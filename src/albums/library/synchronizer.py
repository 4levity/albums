from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Collection, List, Sequence

import humanize
from prompt_toolkit.shortcuts import confirm
from rich.markup import escape
from rich.progress import Progress, TransferSpeedColumn
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..app import Context
from ..config import SyncDestination
from ..database import selector
from ..library.paths import make_template_path
from ..library.transcoder import Transcoder
from ..types import Album
from ..words.make import plural

logger = logging.getLogger(__name__)


@dataclass
class SyncOperations:
    copy_album_paths: list[str] = field(default_factory=list[str])
    copy_bytes: int = 0
    transcode_album_paths: list[str] = field(default_factory=list[str])
    transcode_seconds: float = 0.0
    extraneous_dest_files: set[Path] = field(default_factory=set[Path])


class Synchronizer:
    _ctx: Context
    _dest: SyncDestination
    _transcoder: Transcoder

    def __init__(self, ctx: Context, dest: SyncDestination):
        if str(ctx.config.library) in {"", "."}:
            raise RuntimeError("Synchronizer cannot be initialized without library path")
        self._ctx = ctx
        self._dest = dest
        self._transcoder = Transcoder(self._ctx, self._dest.convert_profile)

    def do_sync(self, delete: bool, force: bool):
        with Session(self._ctx.db) as session:
            ops = self._analyze(session)
            if ops.transcode_album_paths:
                ops.copy_bytes += self._transcode_albums(session, ops.transcode_album_paths, ops.transcode_seconds)
                ops.copy_album_paths.extend(ops.transcode_album_paths)
            if ops.extraneous_dest_files:
                if delete:
                    self._delete_destination_paths(ops.extraneous_dest_files, force)
                else:
                    self._ctx.console.print(
                        f"[bold green]not deleting {plural(ops.extraneous_dest_files, 'path')} from {escape(str(self._dest.path_root))}, e.g. {str(next(iter(ops.extraneous_dest_files)))}"
                    )
            if ops.copy_bytes:
                self._copy_albums(session, ops.copy_album_paths, ops.copy_bytes)
            else:
                self._ctx.console.print("nothing to copy")
        if self._transcoder.initialized:
            self._transcoder.shrink_cache()

    def _analyze(self, session: Session) -> SyncOperations:
        existing_dest_paths = set(self._dest.path_root.rglob("*"))  # loads all paths in destination into a set in memory!
        if self._dest.collection:
            source_albums = selector.load_album_entities(session, regex=False, collection=[self._dest.collection])
        else:
            source_albums = self._ctx.select_album_entities(session)

        skipped_tracks = 0
        ops = SyncOperations()
        for album in source_albums:
            dest_path = self._make_dest_path(album)
            use_transcoded = self._use_transcoded_album(album)

            # remove in-use dirs from destination set if present
            tmp_dest_path = dest_path
            while tmp_dest_path.relative_to(self._dest.path_root).name != "":
                if tmp_dest_path.exists() and not tmp_dest_path.is_dir():
                    logger.error(f"destination {str(tmp_dest_path)} exists, but is not a directory. Aborting.")
                    raise SystemExit(1)
                existing_dest_paths.discard(tmp_dest_path)
                tmp_dest_path = tmp_dest_path.parent

            copy_album = False
            missing_from_transcoder_cache = False
            album_library_size = 0
            copy_cached_tracks_size = 0
            album_length = 0.0
            for track in sorted(album.tracks):
                album_length += track.stream.length
                album_library_size += track.file_size
                dest_filename = self._converted_track_filename(track.filename) if use_transcoded else track.filename
                dest_track_path: Path = dest_path / dest_filename
                if dest_track_path.exists():
                    if not dest_track_path.is_file():
                        logger.error(f"destination {str(dest_track_path)} exists, but is not a file. Aborting.")
                        raise SystemExit(1)
                    existing_dest_paths.remove(dest_track_path)
                    if use_transcoded:
                        # TODO if transcode, check dest file stat, should be newer than source library file
                        skipped_tracks += 1
                    else:
                        stat = dest_track_path.stat()
                        # treat last-modified within one second as identical due to rounding errors and file system differences
                        different_timestamp = abs(int(stat.st_mtime) - track.modify_timestamp) > 1
                        copy_album |= stat.st_size != track.file_size or different_timestamp
                else:
                    # a track on this album is missing from destination
                    copy_album = True
                    if use_transcoded:
                        cached_track = self._transcoder.in_cache(album, track)
                        if cached_track:
                            copy_cached_tracks_size += cached_track.stat().st_size
                        else:
                            missing_from_transcoder_cache = True

            if copy_album:
                if use_transcoded:
                    if missing_from_transcoder_cache:
                        logger.info(f"transcode: {escape(Path(album.path).name)}")
                        ops.transcode_album_paths.append(album.path)
                        ops.transcode_seconds += album_length
                    else:
                        logger.info(f"copy from transcoder cache: {escape(Path(album.path).name)}")
                        ops.copy_album_paths.append(album.path)
                        ops.copy_bytes += copy_cached_tracks_size
                else:
                    logger.info(f"copy from library: {escape(Path(album.path).name)}")
                    ops.copy_album_paths.append(album.path)
                    ops.copy_bytes += album_library_size
            else:
                skipped_tracks += len(album.tracks)

        if skipped_tracks > 0:
            self._ctx.console.print(f"Skipping {plural(skipped_tracks, 'existing track')}")
        ops.extraneous_dest_files = existing_dest_paths
        return ops

    def _delete_destination_paths(self, delete_paths: Collection[Path], force: bool):
        self._ctx.console.print(f"[orange]will delete {plural(delete_paths, 'path')} from {escape(str(self._dest.path_root))}")
        if force or confirm("are you sure you want to delete?"):
            self._ctx.console.print("[bold red]deleting files from destination")
            for delete_path in sorted(delete_paths, reverse=True):
                if delete_path.is_dir():
                    delete_path.rmdir()
                else:
                    delete_path.unlink()
                logger.info(f"deleting {delete_path}")
            self._ctx.console.print("done deleting files.")
        else:
            self._ctx.console.print("skipped deleting files from destination")

    def _transcode_albums(self, session: Session, album_paths: Sequence[str], transcode_seconds: float) -> int:
        self._ctx.console.print(f"Transcoding {plural(album_paths, 'album')}, {humanize.naturaldelta(transcode_seconds)} of audio")
        total_bytes = 0
        with Progress(console=self._ctx.console) as progress:
            transcode_task = progress.add_task("Transcoding", total=transcode_seconds)
            for path in album_paths:
                (album,) = session.execute(select(Album).filter(Album.path == path)).tuples().one()
                for track in album.tracks:
                    converted = self._transcoder.get_transcoded(album, track)  # just putting it in the cache
                    total_bytes += converted.stat().st_size
                    progress.update(transcode_task, advance=track.stream.length)
        return total_bytes

    def _copy_albums(self, session: Session, album_paths: List[str], copy_bytes: int):
        self._ctx.console.print(f"Copying {plural(album_paths, 'album')} {humanize.naturalsize(copy_bytes)}")
        with Progress(*Progress.get_default_columns(), TransferSpeedColumn(), console=self._ctx.console) as progress:
            sync_task = progress.add_task("Copying", total=copy_bytes)
            for path in sorted(album_paths):
                (album,) = session.execute(select(Album).filter(Album.path == path)).tuples().one()
                dest_path = self._make_dest_path(album)
                use_transcoded = self._use_transcoded_album(album)
                os.makedirs(dest_path, exist_ok=True)
                for track in album.tracks:
                    if use_transcoded:
                        dest = dest_path / self._converted_track_filename(track.filename)
                        src = self._transcoder.get_transcoded(album, track)  # should already be in cache
                        size = src.stat().st_size
                    else:
                        dest = dest_path / track.filename
                        src = self._ctx.config.library / album.path / track.filename
                        size = track.file_size
                    logger.debug(f"copying to {str(dest)}")
                    shutil.copy2(src, dest)
                    progress.update(sync_task, advance=size)
        self._ctx.console.print("Done copying")

    def _make_dest_path(self, album: Album) -> Path:
        dest_relpath = make_template_path(self._ctx, album, self._dest.relpath_template_artist, self._dest.relpath_template_compilation)
        return self._dest.path_root / (dest_relpath if dest_relpath else album.path)

    def _converted_track_filename(self, original_filename: str):
        suffix = f".{self._dest.convert_profile.split(' ')[-1]}"
        return str(Path(original_filename).with_suffix(suffix))

    def _use_transcoded_album(self, album: Album) -> bool:
        if self._dest.allow_file_types and any(
            str.lower(Path(track.filename).suffix[1:]) not in self._dest.allow_file_types for track in album.tracks
        ):
            return True
        if self._dest.max_kbps and sum(track.stream.bitrate / 1024.0 for track in album.tracks) / len(album.tracks) > self._dest.max_kbps:
            return True
        return False
