import glob
import itertools
import logging
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Callable, Iterator, Mapping

from rbloom import Bloom
from rich.markup import escape
from rich.progress import Progress
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from albums.app import SCANNER_VERSION, Context
from albums.entities import Album, ScanHistoryEntity
from albums.library.album_scanner import scan_album
from albums.tagger.folder import AlbumTagger
from albums.words import plural

from .album_scanner import picture_cache
from .scanner_types import AlbumScanResult

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
            try:
                (albums_total, any_changes) = scan(ctx, session, scan_albums, reread)
                if any_changes:
                    session.commit()
                return (albums_total, any_changes)
            finally:
                # Ensure session is always closed
                try:
                    session.close()
                except Exception as ex:
                    logger.warning(repr(ex))

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
        tagger = AlbumTagger(ctx.config.library / path, preload={} if reread else picture_cache(album))
        with session.begin_nested() as path_scan_transaction:
            if album and album.album_id is not None:
                unvisited_album_ids.remove(album.album_id)
                result = scan_album(ctx, tagger, album, reread)
                if result != AlbumScanResult.UNCHANGED or album.scanner != SCANNER_VERSION:
                    if result == AlbumScanResult.REMOVED:
                        session.delete(album)
                    elif result != AlbumScanResult.UNCHANGED:
                        album.modified_at = int(datetime.now(UTC).timestamp())
                    album.scanner = SCANNER_VERSION
                    path_scan_transaction.commit()
            else:
                album = Album(path=path, scanner=SCANNER_VERSION)
                new_result = scan_album(ctx, tagger, album, False)
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
        tagger = AlbumTagger(ctx.config.library / album.path, preload={} if reread else picture_cache(album))
        with session.begin_nested() as album_scan_transaction:
            result = scan_album(ctx, tagger, album, reread)
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
