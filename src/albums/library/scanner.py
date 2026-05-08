import glob
import itertools
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Final, Iterator, List, Mapping, Tuple

import humanize
from rbloom import Bloom
from rich.markup import escape
from rich.progress import Progress
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from ..app import SCANNER_VERSION, Context
from ..picture.format import format_to_mime_type
from ..picture.scan import PictureScannerCache
from ..tagger.folder import AUDIO_FILE_SUFFIXES, AlbumTagger
from ..types import Album, OtherFile, PictureFile, ScanHistoryEntity, TagV, Track, TrackPicture
from ..words.make import plural
from .folder import MiniStat, read_binary_file, stat_dir

MAX_IMAGE_SIZE: Final = 128 * 1024 * 1024  # don't load and scan image files larger than this. 16 MB is the max for ID3v2 and FLAC tags.


class AlbumScanResult(Enum):
    NO_TRACKS = auto()
    NEW = auto()
    UPDATED = auto()
    UNCHANGED = auto()
    REMOVED = auto()


@dataclass(frozen=True)
class TargetRescan:
    source: PictureFile | Track | OtherFile
    tags: bool
    images: bool
    streams: bool


logger = logging.getLogger(__name__)


def scan(
    ctx: Context,
    session: Session | None = None,
    scan_albums: Iterator[Album] | None = None,
    reread: bool = False,
    check_first_full_scan_path_count: Callable[[int], None] = lambda _: None,
) -> tuple[int, bool]:
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
        last_folders = session.execute(select(ScanHistoryEntity.folders_scanned).order_by(desc(ScanHistoryEntity.timestamp))).first()
        if last_folders:
            # make scan faster while retaining progress bar by using last scan stats for approx folder count
            paths = glob.iglob("**/", root_dir=ctx.config.library, recursive=True)
            # estimate more folders than last scan to maybe avoid progress bar hanging at 100% if albums were added
            expected_path_count = int(last_folders[0] * 1.01)
            logger.info(f"expect to scan about {expected_path_count} paths")
        else:
            with ctx.console.status(f"finding folders in {escape(str(ctx.config.library))}", spinner="bouncingBar"):
                path_list = glob.glob("**/", root_dir=ctx.config.library, recursive=True)
            paths = iter(path_list)
            expected_path_count = len(path_list)
            check_first_full_scan_path_count(expected_path_count)
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
        any_changes = any(scan_results.get(k) for k in [AlbumScanResult.NEW, AlbumScanResult.UPDATED, AlbumScanResult.REMOVED])
        if full_scan:
            session.add(ScanHistoryEntity(timestamp=int(time.time()), folders_scanned=scanned, albums_total=albums_total))
        session.flush()
    except KeyboardInterrupt:
        session.commit()  # nested transaction should have rolled back, but commit completed scans
        logger.error("scan interrupted, exiting")
        raise SystemExit(1)

    if ctx.verbose:
        ctx.console.print(f"scanned {plural(scanned, 'folder')} in {escape(str(ctx.config.library))} in {int(time.perf_counter() - start_time)}s.")
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
        tagger = AlbumTagger(ctx.config.library / path, preload={} if reread else _picture_cache(album))
        with session.begin_nested() as path_scan_transaction:
            if album and album.album_id is not None:
                unvisited_album_ids.remove(album.album_id)
                result = _scan_album(ctx, tagger, album, reread)
                if result != AlbumScanResult.UNCHANGED or album.scanner != SCANNER_VERSION:
                    if result == AlbumScanResult.REMOVED:
                        session.delete(album)
                    elif result != AlbumScanResult.UNCHANGED:
                        album.modified_at = int(datetime.now(UTC).timestamp())
                    album.scanner = SCANNER_VERSION
                    path_scan_transaction.commit()
            else:
                album = Album(path=path, scanner=SCANNER_VERSION)
                new_result = _scan_album(ctx, tagger, album, False)
                if new_result == AlbumScanResult.UPDATED:
                    result = AlbumScanResult.NEW
                    session.add(album)
                    path_scan_transaction.commit()
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
        tagger = AlbumTagger(ctx.config.library / album.path, preload={} if reread else _picture_cache(album))
        with session.begin_nested() as album_scan_transaction:
            result = _scan_album(ctx, tagger, album, reread)
            scan_results[result] += 1
            if result != AlbumScanResult.UNCHANGED or album.scanner != SCANNER_VERSION:
                if result == AlbumScanResult.REMOVED:
                    session.delete(album)
                elif result != AlbumScanResult.UNCHANGED:
                    album.modified_at = int(datetime.now(UTC).timestamp())
                album.scanner = SCANNER_VERSION
                album_scan_transaction.commit()
        update_progress()
    return scan_results


def _picture_cache(album: Album | None) -> PictureScannerCache:
    if not album:
        return {}
    return dict(
        itertools.chain(
            (
                ((pic.picture_info.file_size, pic.picture_info.file_hash), pic.picture_info)
                for track in sorted(album.tracks)
                for pic in track.pictures
            ),
            (((file.picture_info.file_size, file.picture_info.file_hash), file.picture_info) for file in sorted(album.picture_files)),
        )
    )


def _scan_track(tagger: AlbumTagger, filename: str, stat: MiniStat, target_scan: TargetRescan | None) -> Track | None:
    with tagger.open(filename) as file:
        if (target_scan is None or target_scan.streams) and file.has_video():
            return None

        if target_scan is not None and not target_scan.tags and isinstance(target_scan.source, Track):
            tags = [TagV(tag=t.tag, value=t.value) for t in target_scan.source.tags]  # we could probably update the existing track instead.
        else:
            tags = [TagV(tag=tag, value=value) for tag, values in file.get_tags() for value in values]

        if target_scan is not None and not target_scan.images and isinstance(target_scan.source, Track):
            pictures = [
                TrackPicture(picture_type=p.picture_type, picture_info=p.picture_info, description=p.description, embed_ix=p.embed_ix)
                for p in target_scan.source.pictures
            ]
        else:
            pictures = [
                TrackPicture(picture_type=picture.type, picture_info=picture.picture_info, description=picture.description, embed_ix=embed_ix)
                for embed_ix, picture in enumerate(picture for (picture, _data) in file.get_pictures())
            ]

        if target_scan is not None and not target_scan.streams and isinstance(target_scan.source, Track):
            stream = target_scan.source.stream
        else:
            stream = file.get_stream_info()

        return Track(
            filename=filename,
            file_size=stat.file_size,
            modify_timestamp=stat.modify_timestamp,
            stream=stream,
            pictures=pictures,
            tags=tags,
        )


def _scan_picture_file(tagger: AlbumTagger, filename: str, stat: MiniStat, scan_target: TargetRescan | None) -> PictureFile | None:
    if scan_target is not None and not scan_target.images and isinstance(scan_target.source, PictureFile):
        p = scan_target.source
        return PictureFile(filename=p.filename, modify_timestamp=p.modify_timestamp, cover_source=p.cover_source, picture_info=p.picture_info)

    if stat.file_size > MAX_IMAGE_SIZE:
        size = humanize.naturalsize(stat.file_size, binary=True)
        max = humanize.naturalsize(MAX_IMAGE_SIZE, binary=True)
        logger.warning(f"skipping image file {str(filename)} because it is {size} (albums max = {max})")
        return None

    expect_mime_type = format_to_mime_type(Path(filename).suffix.replace(".", ""))
    picture_info = tagger.get_picture_scanner().scan(read_binary_file(tagger.path() / filename), expect_mime_type)
    return PictureFile(filename=filename, modify_timestamp=stat.modify_timestamp, cover_source=False, picture_info=picture_info)


def _scan_file(album: Album, tagger: AlbumTagger, path: Path, stat: MiniStat, target_scan: TargetRescan | None) -> None:
    cover_source = _remove_file(album, path.name)

    if str.lower(path.suffix) in AUDIO_FILE_SUFFIXES:
        new_track = _scan_track(tagger, path.name, stat, target_scan)
        if new_track is None:
            album.other_files.append(OtherFile(filename=path.name, file_size=stat.file_size, modify_timestamp=stat.modify_timestamp))
        else:
            album.tracks.append(new_track)
    else:
        new_picture_file = _scan_picture_file(tagger, path.name, stat, target_scan)
        if new_picture_file is None:
            album.other_files.append(OtherFile(filename=path.name, file_size=stat.file_size, modify_timestamp=stat.modify_timestamp))
        else:
            new_picture_file.cover_source = cover_source
            album.picture_files.append(new_picture_file)


def _remove_file(album: Album, filename: str) -> bool:
    while (to_remove := next((o for o in album.other_files if o.filename == filename), None)) is not None:
        album.other_files.remove(to_remove)
    while (to_remove := next((t for t in album.tracks if t.filename == filename), None)) is not None:
        album.tracks.remove(to_remove)
    removed_cover_source = False
    while (original := next((f for f in album.picture_files if f.filename == filename), None)) is not None:
        removed_cover_source |= original.cover_source
        album.picture_files.remove(original)
    return removed_cover_source


def _scan_album(ctx: Context, tagger: AlbumTagger, album: Album, reread: bool = False) -> AlbumScanResult:
    album_path = ctx.config.library / album.path
    stored_files_list: List[Tuple[str, Tuple[MiniStat, PictureFile | Track | OtherFile]]] = [
        (t.filename, (MiniStat(t.file_size, t.modify_timestamp), t)) for t in album.tracks
    ]
    stored_files_list.extend((f.filename, (MiniStat(f.picture_info.file_size, f.modify_timestamp), f)) for f in album.picture_files)
    stored_files_list.extend((o.filename, (MiniStat(o.file_size, o.modify_timestamp), o)) for o in album.other_files)
    duplicate_files = set(filename for (filename, _) in stored_files_list if sum(1 if filename == fn else 0 for (fn, _) in stored_files_list) > 1)
    stored_files = dict(stored_files_list)
    updated = False
    for path, stat in stat_dir(album_path):
        if path.name in stored_files:
            (stored_stat, file) = stored_files[path.name]
            targeted = None
            if reread or stat != stored_stat or path.name in duplicate_files or (targeted := _needs_rescan(album.scanner, file)):
                logger.debug(f"re-scanning file: {str(path)}")
                _scan_file(album, tagger, path, stat, targeted)
                updated = True  # TODO if reread==True, check whether file actually changed
            del stored_files[path.name]
        else:
            logger.debug(f"scanning new file: {str(path)}")
            _scan_file(album, tagger, path, stat, None)
            updated = True
    for filename in stored_files:  # anything left has been deleted
        _remove_file(album, filename)
        updated = True
    if len(album.tracks) == 0:
        return AlbumScanResult.REMOVED
    return AlbumScanResult.UPDATED if updated else AlbumScanResult.UNCHANGED


def _needs_rescan(scanner: int, file: Track | PictureFile | OtherFile) -> TargetRescan | None:
    if scanner < 6:
        return TargetRescan(file, tags=True, images=True, streams=True)
    if scanner < 7:
        return TargetRescan(file, tags=False, images=False, streams=True)
    return None
