import glob
import logging
from rich.markup import escape
from rich.progress import Progress
import time

import albums.database.operations
from .. import app
from .folder import scan_folder, AlbumScanResult


logger = logging.getLogger(__name__)


DEFAULT_SUPPORTED_FILE_TYPES = [".flac", ".mp3", ".m4a", ".wma", ".ogg"]


def scan(ctx: app.Context, path_selector=None, reread=False):
    suffixes = [str.lower(suffix) for suffix in ctx.config.get("locations", {}).get("supported_file_types", DEFAULT_SUPPORTED_FILE_TYPES)]
    start_time = time.perf_counter()

    if path_selector is not None:
        stored_paths = path_selector()
    else:
        stored_paths = ctx.db.execute("SELECT path, album_id FROM album;")
    unprocessed_albums = dict(((path, album_id) for (path, album_id) in stored_paths))

    scanned = 0
    scan_results: dict[AlbumScanResult, int] = dict([(r.name, 0) for r in AlbumScanResult])
    try:
        with ctx.console.status(
            f"finding folders in {'specified folders' if path_selector else escape(str(ctx.library_root))}", spinner="bouncingBar"
        ):
            if path_selector is not None:
                paths = list(path for path in unprocessed_albums.keys() if (ctx.library_root / path).exists())
            else:
                # TODO: instead of preloading, use iglob and guess total number of paths based on last scan, or something
                paths = glob.glob("**/", root_dir=ctx.library_root, recursive=True)

        with Progress(console=ctx.console) as progress:
            scan_task = progress.add_task("Scanning", total=len(paths))
            for path_str in paths:
                album_id = unprocessed_albums.get(path_str)
                if album_id is None:
                    stored_album = None
                else:
                    del unprocessed_albums[path_str]
                    stored_album = albums.database.operations.load_album(ctx.db, album_id, True)

                (album, result) = scan_folder(ctx.library_root, path_str, suffixes, stored_album, reread)
                scan_results[result.name] += 1

                if result == AlbumScanResult.UNCHANGED:
                    logger.debug(f"no changes detected for album {album.path}")
                elif result == AlbumScanResult.NEW:
                    logger.debug(f"add album {album.path}")
                    albums.database.operations.add(ctx.db, album)
                elif result == AlbumScanResult.UPDATED:
                    logger.debug(f"update track info for album {album.path}")
                    albums.database.operations.update_tracks(ctx.db, album_id, album.tracks)
                elif result == AlbumScanResult.NO_TRACKS:
                    if album_id:
                        logger.info(f"remove album {stored_album.album_id} {stored_album.path}")
                        albums.database.operations.remove(ctx.db, album_id)
                else:
                    raise ValueError(f"invalid AlbumScanResult {result} for path {path_str}")
                scanned += 1
                progress.update(scan_task, advance=1)

        # remaining entries in unchecked_albums are apparently no longer in the library
        for path, album_id in unprocessed_albums.items():
            logger.info(f"remove album {album_id} {path}")
            albums.database.operations.remove(ctx.db, album_id)

    except KeyboardInterrupt:
        logger.error("scan interrupted, exiting")

    ctx.db.commit()
    ctx.console.print(f"scanned {scanned} folders in {escape(str(ctx.library_root))} in {int(time.perf_counter() - start_time)}s.")
    ctx.console.print(scan_results)
