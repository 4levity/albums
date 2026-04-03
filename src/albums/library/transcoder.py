import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from rich.markup import escape

from ..app import Context
from ..tagger.provider import AlbumTaggerProvider
from ..types import Album, Track

logger = logging.getLogger(__name__)


class Transcoder:
    ctx: Context
    file_type: str

    _tagger: AlbumTaggerProvider
    _this_cache: Path
    _ffmpeg_options: Sequence[str]

    def __init__(self, ctx: Context, profile: str):
        ensure_ffmpeg()

        self.ctx = ctx
        parts = profile.split(" ")
        self.file_type = parts[-1]
        self._ffmpeg_options = parts[:-1]
        self._tagger = AlbumTaggerProvider(ctx.config.library, id3v1=ctx.config.id3v1)
        self._create_cache_dirs()

    # TODO invalidate cached track when source library track is newer

    def in_cache(self, album: Album, track: Track) -> Path | None:
        cache_path = self._cache_path(album.path, track.filename)
        return cache_path if cache_path.exists() else None

    def get_transcoded(self, album: Album, track: Track) -> Path:
        cache_path = self._cache_path(album.path, track.filename)
        if cache_path.exists():
            return cache_path

        self._transcode(self.ctx.config.library / album.path, track, cache_path)
        return cache_path

    def _cache_path(self, album_path: str, source_filename: str) -> Path:
        return (self._this_cache / album_path / source_filename).with_suffix(f".{self.file_type}")

    def _transcode(self, album_path: Path, track: Track, dest: Path):
        run_ffmpeg(["-i", track.filename, *self._ffmpeg_options, str(dest)], cwd=album_path)
        # TODO track cache size, remove files from other sets if needed

        with self._tagger.get(dest.parent).open(dest.name) as dest_tags:
            for tag, value in track.tag_dict().items():
                dest_tags.set_tag(tag, value)
            if track.pictures:
                with self._tagger.get(album_path).open(track.filename) as src_tags:
                    for pic, image_data in src_tags.get_pictures():
                        dest_tags.add_picture(pic, image_data)

    def _create_cache_dirs(self):
        cache = self.ctx.config.transcoder_cache
        if cache.exists() and not cache.is_dir():
            raise RuntimeError(f"transcoder cache exists but is not a directory: {str(cache)}")

        if not cache.exists():
            self.ctx.console.print(f"Creating transcoder cache: {escape(str(cache))}")
            os.mkdir(cache)
        # TODO measure cache but don't flush this option cache

        descriptor = f"{' '.join(self._ffmpeg_options)} {self.file_type}"
        self._this_cache = self.ctx.config.transcoder_cache / f"{hash(descriptor):x}"
        if self._this_cache.exists():
            if not self._this_cache.is_dir():
                raise RuntimeError(f"exists but not a directory: {str(self._this_cache)}")
        else:
            os.mkdir(self._this_cache)

        index_file = self.ctx.config.transcoder_cache / "index.json"
        index: dict[str, str] = json.loads(index_file.read_text()) if index_file.exists() else {}
        index[descriptor] = self._this_cache.name
        index_file.write_text(json.dumps(index))


def ensure_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        logger.error("ffmpeg not found on path - aborting because transcoding is unavailable")
        raise SystemExit(1)


def run_ffmpeg(args: Sequence[str], cwd: Path) -> None:
    result = subprocess.run(["ffmpeg", *args], cwd=cwd)
    if result.returncode != 0:
        logger.error(f"failed to run ffmpeg, exit code = {result.returncode}")
