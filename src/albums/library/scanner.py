import glob
import itertools
import logging
import mimetypes
import time
from collections import defaultdict
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Iterator, Mapping

import humanize
from rbloom import Bloom
from rich.markup import escape
from rich.progress import Progress
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from ..app import SCANNER_VERSION, Context
from ..picture.scan import PictureScannerCache
from ..tagger.folder import AUDIO_FILE_SUFFIXES, AlbumTagger
from ..types import Album, PictureFile, ScanHistoryEntity, Tag, Track, TrackPicture
from .folder import Ministat, read_binary_file, stat_dir

MAX_IMAGE_SIZE = 128 * 1024 * 1024  # don't load and scan image files larger than this. 16 MB is the max for ID3v2 and FLAC tags.


class AlbumScanResult(Enum):
    NO_TRACKS = auto()
    NEW = auto()
    UPDATED = auto()
    UNCHANGED = auto()
    REMOVED = auto()


logger = logging.getLogger(__name__)


def scan(ctx: Context, session: Session | None = None, scan_albums: Iterator[Album] | None = None, reread: bool = False) -> tuple[int, bool]:
    if session is None:
        with Session(ctx.db) as session:
            (albums_total, any_changes) = scan(ctx, session, scan_albums, reread)
            if any_changes:
                session.commit()
            return (albums_total, any_changes)

    start_time = time.perf_counter()
    expected_path_count = 0
    paths: Iterator[str] | None = None
    full_scan = not scan_albums
    if full_scan:
        last_folders_scanned = session.scalar(select(ScanHistoryEntity.folders_scanned).order_by(desc(ScanHistoryEntity.timestamp)))
        if last_folders_scanned:
            # make scan faster while retaining progress bar by using last scan stats for approx folder count
            paths = glob.iglob("**/", root_dir=ctx.config.library, recursive=True)
            # estimate more folders than last scan to maybe avoid progress bar hanging at 100% if albums were added
            expected_path_count = int(last_folders_scanned * 1.01)
        else:
            with ctx.console.status(f"finding folders in {escape(str(ctx.config.library))}", spinner="bouncingBar"):
                path_list = glob.glob("**/", root_dir=ctx.config.library, recursive=True)
            paths = iter(path_list)
            expected_path_count = len(path_list)
        paths = itertools.chain(["."], paths)

    def do_scan(update_progress: Callable[[], None] = lambda: None):
        if scan_albums:
            return rescan_albums(ctx, session, scan_albums, update_progress, reread)
        elif paths:
            return scan_library(ctx, session, paths, update_progress, reread)
        else:
            raise RuntimeError()

    try:
        if full_scan and ctx.console.is_interactive:
            with Progress(console=ctx.console) as progress:
                scan_task = progress.add_task("Scanning", total=expected_path_count)
                scan_results = do_scan(lambda: progress.update(scan_task, advance=1))
                progress.update(scan_task, completed=expected_path_count)
        elif ctx.console.is_interactive:
            with ctx.console.status("Scanning albums", spinner="bouncingBar"):
                scan_results = do_scan()
        else:
            scan_results = do_scan()

        scanned = sum(scan_results.values())
        albums_total = scan_results[AlbumScanResult.NEW] + scan_results[AlbumScanResult.UPDATED] + scan_results[AlbumScanResult.UNCHANGED]
        any_changes = any(k in scan_results for k in [AlbumScanResult.NEW, AlbumScanResult.UPDATED, AlbumScanResult.REMOVED])
        if full_scan:
            session.add(ScanHistoryEntity(timestamp=int(time.perf_counter()), folders_scanned=scanned, albums_total=albums_total))
        session.flush()
    except KeyboardInterrupt:
        session.commit()  # nested transaction should have rolled back, but commit completed scans
        logger.error("scan interrupted, exiting")
        raise SystemExit(1)

    if ctx.verbose:
        ctx.console.print(f"scanned {scanned} folders in {escape(str(ctx.config.library))} in {int(time.perf_counter() - start_time)}s.")
        ctx.console.print(", ".join(f"{str.lower(k.name).replace('_', ' ')}: {v}" for (k, v) in scan_results.items()))

    return (albums_total, any_changes)


def scan_library(
    ctx: Context, session: Session, paths: Iterator[str], update_progress: Callable[[], None], reread: bool = False
) -> Mapping[AlbumScanResult, int]:
    current_album_paths = Bloom(100000, 0.01)
    unvisited_album_ids: set[int] = set()
    for (
        album_id,
        path,
    ) in session.execute(select(Album.album_id, Album.path)).tuples():
        if album_id is not None:  # it's not
            current_album_paths.add(path)
            unvisited_album_ids.add(album_id)
    scan_results: defaultdict[AlbumScanResult, int] = defaultdict(int)
    for path in paths:
        if path in current_album_paths:  # 99% chance
            album_match = session.execute(select(Album).where(Album.path == path)).tuples().one_or_none() or (None,)
        else:
            album_match = (None,)
        (album,) = album_match
        tagger = AlbumTagger(ctx.config.library / path, preload=_picture_cache(album))
        with session.begin_nested() as path_scan_transacion:
            if album and album.album_id is not None:
                unvisited_album_ids.remove(album.album_id)
                result = _scan_album(ctx, tagger, album, reread)
                if result != AlbumScanResult.UNCHANGED or album.scanner != SCANNER_VERSION:
                    if result == AlbumScanResult.REMOVED:
                        session.delete(album)
                    else:
                        album.scanner = SCANNER_VERSION
                    path_scan_transacion.commit()
            else:
                album = Album(path=path, scanner=SCANNER_VERSION)
                new_result = _scan_album(ctx, tagger, album, False)
                if new_result == AlbumScanResult.UPDATED:
                    result = AlbumScanResult.NEW
                    session.add(album)
                    path_scan_transacion.commit()
                else:
                    result = AlbumScanResult.NO_TRACKS
        if result not in {AlbumScanResult.NO_TRACKS, AlbumScanResult.UNCHANGED}:
            logger.info(f"{result.name} album {path}")
        scan_results[result] += 1
        update_progress()

    for album_id in unvisited_album_ids:
        scan_results[AlbumScanResult.REMOVED] += 1
        logger.info(f"{AlbumScanResult.REMOVED.name} album {album_id} (not found)")
        session.execute(delete(Album).where(Album.album_id == album_id))
    return scan_results


def rescan_albums(
    ctx: Context, session: Session, scan_albums: Iterator[Album], update_progress: Callable[[], None], reread: bool = False
) -> Mapping[AlbumScanResult, int]:
    scan_results: defaultdict[AlbumScanResult, int] = defaultdict(int)
    for album in scan_albums:
        tagger = AlbumTagger(ctx.config.library / album.path, preload=_picture_cache(album))
        with session.begin_nested() as album_scan_transaction:
            result = _scan_album(ctx, tagger, album, reread)
            scan_results[result] += 1
            if result != AlbumScanResult.UNCHANGED or album.scanner != SCANNER_VERSION:
                if result == AlbumScanResult.REMOVED:
                    session.execute(delete(Album).where(Album.album_id == album.album_id))
                album.scanner = SCANNER_VERSION
                album_scan_transaction.commit()
        update_progress()
    return scan_results


def _picture_cache(album: Album | None) -> PictureScannerCache:
    if not album:
        return {}
    return dict(
        itertools.chain(
            (((pic.picture_info.file_size, pic.picture_info.file_hash), pic.picture_info) for track in album.tracks for pic in track.pictures),
            (((file.picture_info.file_size, file.picture_info.file_hash), file.picture_info) for file in album.picture_files),
        )
    )


def _scan_track(tagger: AlbumTagger, filename: str, stat: Ministat):
    with tagger.open(filename) as tags:
        scan_result = tags.scan()
        tags = [Tag(tag=tag, value=value) for tag, values in scan_result.tags for value in values]
        pictures = [
            TrackPicture(picture_type=picture.type, picture_info=picture.picture_info, description=picture.description, embed_ix=embed_ix)
            for embed_ix, picture in enumerate(scan_result.pictures)
        ]
        return Track(
            filename=filename,
            file_size=stat.file_size,
            modify_timestamp=stat.modify_timestamp,
            stream=scan_result.stream,
            pictures=pictures,
            tags=tags,
        )


def _scan_picture_file(tagger: AlbumTagger, filename: str, stat: Ministat):
    if stat.file_size > MAX_IMAGE_SIZE:
        size = humanize.naturalsize(stat.file_size, binary=True)
        max = humanize.naturalsize(MAX_IMAGE_SIZE, binary=True)
        logger.warning(f"skipping image file {str(filename)} because it is {size} (albums max = {max})")
        # TODO: record the existence of the large image even if we do not load its metadata, just like we would with a load error
        # Note: recording images that are valid but lack metadata would cause issues with detecting duplicates and assigning cover art
        return None

    expect_mime_type, _ = mimetypes.guess_type(filename)
    picture_info = tagger.get_picture_scanner().scan(read_binary_file(tagger.path() / filename), expect_mime_type)
    return PictureFile(filename=filename, modify_timestamp=stat.modify_timestamp, cover_source=False, picture_info=picture_info)


def _scan_file(album: Album, tagger: AlbumTagger, path: Path, stat: Ministat, replace: bool) -> None:
    if str.lower(path.suffix) in AUDIO_FILE_SUFFIXES:
        if replace:
            while (to_remove := next((t for t in album.tracks if t.filename == path.name), None)) is not None:
                album.tracks.remove(to_remove)
        album.tracks.append(_scan_track(tagger, path.name, stat))
    else:
        cover_source = False
        if replace:
            while (original := next((f for f in album.picture_files if f.filename == path.name), None)) is not None:
                cover_source = original.cover_source
                album.picture_files.remove(original)
        new_picture_file = _scan_picture_file(tagger, path.name, stat)
        if new_picture_file:
            new_picture_file.cover_source = cover_source
            album.picture_files.append(new_picture_file)


def _scan_album(ctx: Context, tagger: AlbumTagger, album: Album, reread: bool = False) -> AlbumScanResult:
    album_path = ctx.config.library / album.path
    stored_files_list = [(t.filename, Ministat(t.file_size, t.modify_timestamp)) for t in album.tracks] + [
        (f.filename, Ministat(f.picture_info.file_size, f.modify_timestamp)) for f in album.picture_files
    ]
    duplicate_files = set(filename for (filename, _) in stored_files_list if sum(1 if filename == fn else 0 for (fn, _) in stored_files_list) > 1)
    stored_files = dict(stored_files_list)
    updated = False
    for path, stat in stat_dir(album_path):
        if path.name in stored_files:
            if reread or stat != stored_files[path.name] or path.name in duplicate_files:
                logger.debug(f"re-scanning file: {str(path)}")
                _scan_file(album, tagger, path, stat, True)
                updated = True  # TODO if reread==True, check whether file actually changed
            del stored_files[path.name]
        else:
            logger.debug(f"scanning new file: {str(path)}")
            _scan_file(album, tagger, path, stat, False)
            updated = True
    for filename in stored_files:  # anything left has been deleted
        if Path(filename).suffix in AUDIO_FILE_SUFFIXES:
            album.tracks.remove(next(t for t in album.tracks if t.filename == filename))
        else:
            album.picture_files.remove(next(f for f in album.picture_files if f.filename == filename))
        updated = True
    if len(album.tracks) == 0:
        return AlbumScanResult.REMOVED
    return AlbumScanResult.UPDATED if updated else AlbumScanResult.UNCHANGED
