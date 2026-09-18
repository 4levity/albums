"""Scan the library (or a set of albums) into the database, tracking added, updated and removed albums."""

import logging
import os
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Callable, Iterator, Mapping

from rich.markup import escape
from rich.progress import Progress
from sqlalchemy import delete, desc, insert, select
from sqlalchemy.orm import Session, selectinload

from albums.app import Context
from albums.entities import Album, LibraryFolder, ScanHistoryEntity, Track
from albums.library.album_scanner import scan_album
from albums.tagger import AlbumTagger
from albums.words import plural

from .album_scanner import picture_cache
from .folder import walk_paths
from .rescan import SCANNER_VERSION
from .scanner_types import AlbumScanResult

logger = logging.getLogger(__name__)


def run_scan(
    ctx: Context,
    session: Session | None = None,
    scan_albums: Iterator[Album] | None = None,
    reread: bool = False,
    check_first_full_scan_path_count: Callable[[int], None] = lambda _: None,
) -> tuple[int, bool]:
    """Scan the library (full scan, or a specific set of albums) and record the results.

    Args:
        session: If ``None``, a session is opened on ``ctx.db`` and committed (when changes occurred)
            and closed when the scan is complete; otherwise the caller owns the transaction.

    Returns:
        Tuple of total album count and whether anything changed.
    """
    if session is None:
        with Session(ctx.db) as session:
            try:
                (albums_total, any_changes) = run_scan(ctx, session, scan_albums, reread)
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
            # speed up scanning (progress bar included) by approximating the folder count from the last scan
            paths = walk_paths(ctx.config.library)
            # over-estimate slightly so the progress bar doesn't stick at 100% if albums were added since
            expected_path_count = int(last_folders[0] * 1.01)
            logger.info(f"expect to scan about {expected_path_count} paths")
        else:
            with ctx.console.status(f"finding folders in {escape(str(ctx.config.library))}", spinner="bouncingBar"):
                path_list = list(walk_paths(ctx.config.library))
            paths = iter(path_list)
            expected_path_count = len(path_list)
            check_first_full_scan_path_count(expected_path_count)

    def do_scan(update_progress: Callable[[], None] = lambda: None) -> tuple[Mapping[AlbumScanResult, int], bool]:
        """Scan, returning the per-result counts and whether the library folder table changed."""
        if scan_albums:
            return (rescan_albums(ctx, session, scan_albums, update_progress, reread), False)
        elif paths:
            return scan_library(ctx, session, paths, update_progress, reread)
        else:
            raise RuntimeError()

    try:
        if full_scan and ctx.console.is_interactive:
            with Progress(console=ctx.console) as progress:
                scan_task = progress.add_task("Scanning", total=expected_path_count)
                (scan_results, folders_changed) = do_scan(lambda: progress.update(scan_task, advance=1))
                progress.update(scan_task, completed=expected_path_count)
        elif ctx.console.is_interactive:
            with ctx.console.status("Scanning albums", spinner="bouncingBar"):
                (scan_results, folders_changed) = do_scan()
        else:
            (scan_results, folders_changed) = do_scan()

        scanned = sum(scan_results.values())
        albums_total = scan_results[AlbumScanResult.NEW] + scan_results[AlbumScanResult.UPDATED] + scan_results[AlbumScanResult.UNCHANGED]
        any_changes = any(scan_results.get(k) for k in [AlbumScanResult.NEW, AlbumScanResult.UPDATED, AlbumScanResult.REMOVED]) or folders_changed
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
) -> tuple[Mapping[AlbumScanResult, int], bool]:
    """Scan every folder path in the library, adding, updating or removing albums as needed.

    Also updates the library_folder table with the walked folders; the returned tuple includes
    whether that table changed.
    """
    albums_by_path: dict[str, Album] = {
        album.path: album
        for album in session.execute(
            select(Album).options(
                selectinload(Album.tracks).selectinload(Track.pictures),
                selectinload(Album.picture_files),
                selectinload(Album.other_files),
            )
        )
        .scalars()
        .unique()
    }
    unvisited_album_ids = {album.album_id for album in albums_by_path.values() if album.album_id is not None}
    scan_results: defaultdict[AlbumScanResult, int] = defaultdict(int)
    walked_paths: set[str] = set()
    for path in paths:
        walked_paths.add(path)
        album = albums_by_path.get(path)
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
    folders_changed = sync_library_folders(session, walked_paths)
    return (scan_results, folders_changed)


def _folder_parent_name(rel_path: str) -> tuple[str, str]:
    """Split a walked relative folder path (trailing separator, not ".") into (parent_path, name).

    The parent path keeps a trailing separator, or is empty for top-level folders.
    """
    stem = rel_path[: -len(os.sep)]
    if os.sep in stem:
        (parent, name) = stem.rsplit(os.sep, 1)
        return (parent + os.sep, name)
    return ("", stem)


def sync_library_folders(session: Session, walked_paths: set[str]) -> bool:
    """Replace the library_folder table with the folders seen during a full scan.

    The table stores every walked folder (album and non-album alike) so checks can find sibling
    folders that differ only in case without reading the file system. Returns whether the table
    contents changed.
    """
    rows: list[dict[str, str]] = []
    walked: set[tuple[str, str]] = set()
    for path in walked_paths:
        if path == ".":
            continue  # the library root itself; its siblings are outside the library
        (parent, name) = _folder_parent_name(path)
        walked.add((parent, name))
        rows.append({"parent_path": parent, "name": name, "name_cf": str.casefold(name)})
    stored = {(parent_path, name) for (parent_path, name) in session.execute(select(LibraryFolder.parent_path, LibraryFolder.name)).tuples()}
    if stored == walked:
        return False
    session.execute(delete(LibraryFolder))
    if rows:  # an ORM insert with no parameter rows emits a single DEFAULT VALUES insert
        session.execute(insert(LibraryFolder), rows)
    return True


def rescan_albums(
    ctx: Context, session: Session, scan_albums: Iterator[Album], update_progress: Callable[[], None], reread: bool = False
) -> Mapping[AlbumScanResult, int]:
    """Re-scan a specific set of albums already in the database."""
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
