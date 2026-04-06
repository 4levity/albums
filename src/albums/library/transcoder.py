from __future__ import annotations

import glob
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from itertools import chain
from os import makedirs, mkdir, unlink
from pathlib import Path
from shutil import rmtree, which
from typing import Sequence

import humanize
import xxhash
from rich.markup import escape

from ..app import Context
from ..tagger.folder import AUDIO_FILE_SUFFIXES
from ..tagger.provider import AlbumTaggerProvider
from ..types import Album, Track

logger = logging.getLogger(__name__)


@dataclass
class CacheStat:
    name: str
    size: int
    timestamp: int

    def __lt__(self, other: CacheStat):
        return self.timestamp < other.timestamp


class Transcoder:
    ctx: Context
    file_type: str
    initialized = False

    _tagger: AlbumTaggerProvider
    _this_cache: Path
    _descriptor: str
    _ffmpeg_options: Sequence[str]
    _cache_stats: dict[str, CacheStat] = {}

    def __init__(self, ctx: Context, profile: str):
        self.ctx = ctx
        parts = profile.split(" ")
        self.file_type = parts[-1]
        self._descriptor = profile
        self._ffmpeg_options = parts[:-1]
        self._tagger = AlbumTaggerProvider(ctx.config.library, id3v1=ctx.config.id3v1)
        self._this_cache = self.ctx.config.transcoder_cache / xxhash.xxh3_64_hexdigest(self._descriptor)

    def in_cache(self, album: Album, track: Track) -> Path | None:
        self._initialize()
        cache_path = self._cache_path(album.path, track.filename)
        return cache_path if cache_path.exists() else None

    def get_transcoded(self, album: Album, track: Track) -> Path:
        self._initialize()
        cache_path = self._cache_path(album.path, track.filename)
        if cache_path.exists():
            return cache_path

        makedirs(self._this_cache / album.path, exist_ok=True)
        self._transcode(self.ctx.config.library / album.path, track, cache_path)
        self._cache_stats[self._this_cache.name].size += cache_path.stat().st_size if cache_path.exists() else 0
        return cache_path

    def shrink_cache(self):
        if sum(c.size for c in self._cache_stats.values()) == 0:
            self._scan_cache()
        cache_max = self.ctx.config.transcoder_cache_size
        while len(self._cache_stats) > 1 and sum(c.size for c in self._cache_stats.values()) > cache_max:
            oldest_other_cache = next((cache for cache in sorted(self._cache_stats.values()) if cache.name != self._this_cache.name))
            logger.info(f"deleting {humanize.naturalsize(oldest_other_cache.size, binary=True)} transcoder cache {oldest_other_cache.name}")
            rmtree(self.ctx.config.transcoder_cache / oldest_other_cache.name)
            del self._cache_stats[oldest_other_cache.name]
            index = dict((k, v) for k, v in self._load_cache_index().items() if v != oldest_other_cache.name)
            self._update_cache_index(index)
        if (total_cache_size := sum(c.size for c in self._cache_stats.values())) > cache_max:
            logger.warning(
                f"after deleting all but the most recently used profile, the transcoder cache size still exceeds configuration: {humanize.naturalsize(total_cache_size, binary=True)}"
            )

    def _cache_path(self, album_path: str, source_filename: str) -> Path:
        return (self._this_cache / album_path / source_filename).with_suffix(f".{self.file_type}")

    def _transcode(self, album_path: Path, track: Track, dest: Path):
        run_ffmpeg(["-i", track.filename, *self._ffmpeg_options, str(dest)], album_path)

        if track.tags or track.pictures:
            with self._tagger.get(dest.parent).open(dest.name) as dest_tags:
                for tag, value in track.tag_dict().items():
                    dest_tags.set_tag(tag, value)
                if track.pictures:
                    with self._tagger.get(album_path).open(track.filename) as src_tags:
                        for pic, image_data in src_tags.get_pictures():
                            dest_tags.add_picture(pic, image_data)

    def _initialize(self):
        if self.initialized:
            return

        ensure_ffmpeg()
        with self.ctx.console.status("Initializing transcoder cache", spinner="bouncingBar"):
            self._create_root_cache()
            self._create_this_cache()
            self._scan_cache()
            self.shrink_cache()

        self.initialized = True

    def _create_root_cache(self):
        cache = self.ctx.config.transcoder_cache
        if cache.exists() and not cache.is_dir():
            raise RuntimeError(f"transcoder cache exists but is not a directory: {str(cache)}")
        if not cache.exists():
            self.ctx.console.print(f"Creating transcoder cache: {escape(str(cache))}")
            mkdir(cache)

    def _create_this_cache(self):
        if self._this_cache.exists() and not self._this_cache.is_dir():
            raise RuntimeError(f"exists but not a directory: {str(self._this_cache)}")
        if self._this_cache.exists():
            self._this_cache.touch()
        else:
            mkdir(self._this_cache)
            self._update_cache_index()

    def _update_cache_index(self, index: dict[str, str] | None = None):
        if index is None:
            index = self._load_cache_index()
            index[self._descriptor] = self._this_cache.name
        (self.ctx.config.transcoder_cache / "index.json").write_text(json.dumps(index), encoding="utf-8")

    def _load_cache_index(self) -> dict[str, str]:
        index_file = self.ctx.config.transcoder_cache / "index.json"
        return json.loads(index_file.read_text()) if index_file.exists() else {}

    def _scan_cache(self):
        index = self._load_cache_index()
        cache_dirs = set(index.values())
        for entry in self.ctx.config.transcoder_cache.iterdir():
            if entry.is_dir():
                if entry.name in cache_dirs:
                    cache_size = self._scan_profile_cache(entry)
                    self._cache_stats[entry.name] = CacheStat(entry.name, cache_size, int(entry.stat().st_mtime))
                else:
                    self.ctx.console.print(f"removing unknown cache dir: {escape(entry.name)}")
                    rmtree(entry)
            elif entry.name != "index.json":
                self.ctx.console.print(f"removing unknown file from cache root: {escape(entry.name)}")
                unlink(entry)

    def _scan_profile_cache(self, cache: Path) -> int:
        size_bytes = 0
        for path in chain(iter(["."]), glob.iglob("**/", root_dir=cache, recursive=True)):
            library_path = self.ctx.config.library / path
            if library_path.is_dir():
                size_bytes += self._scan_cache_dir(cache, path, library_path)
            else:
                logger.info(f"removing unknown folder, cache {cache.name}: {escape(path)}")
                rmtree(cache / path)
        return size_bytes

    def _scan_cache_dir(self, cache: Path, path: str, library_path: Path) -> int:
        size_bytes = 0
        for entry in (cache / path).iterdir():
            if entry.is_dir():
                continue
            library_match = next(
                (
                    library_track
                    for library_track in library_path.glob(f"{entry.stem}.*")
                    if (library_track.stem == entry.stem and library_track.suffix in AUDIO_FILE_SUFFIXES)
                ),
                None,
            )
            if library_match is not None:
                stat = entry.stat()
                if (library_match.stat().st_mtime - 1.0) < stat.st_mtime:
                    size_bytes += stat.st_size  # keep for now
                else:
                    logger.debug(f"delete from cache, library file newer: {path}{os.sep}{entry.name}")
                    unlink(entry)  # older than library file
            else:
                logger.debug(f"delete from cache, not in library: {path}{os.sep}{entry.name}")
                unlink(entry)  # not in library any more

        return size_bytes


def ensure_ffmpeg() -> None:
    if not which("ffmpeg"):
        logger.error("ffmpeg not found on path - aborting because transcoding is unavailable")
        raise SystemExit(1)


def run_ffmpeg(args: Sequence[str], cwd: Path) -> None:
    result = subprocess.run(["ffmpeg", *args], cwd=cwd)
    if result.returncode != 0:
        logger.error(f"failed to run ffmpeg, exit code = {result.returncode}")
