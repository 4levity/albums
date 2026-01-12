import click
import glob
import logging
from pathlib import Path
import sqlite3
import time
from albums import database
from albums import tags
from albums import tools


logger = logging.getLogger(__name__)
TRACK_SUFFIXES = [".flac", ".mp3", ".m4a"]


def track_files_modified(tracks1: list[dict], tracks2: list[dict]):
    if len(tracks1) != len(tracks2):
        return True
    for index, t1 in enumerate(tracks1):
        t2 = tracks2[index]
        if t1["SourceFile"] != t2["SourceFile"] or t1["FileSize"] != t2["FileSize"] or t1["FileModifyDate"] != t2["FileModifyDate"]:
            return True
    return False


def scan(db: sqlite3.Connection, library_root: Path):
    start_time = time.perf_counter()

    unchecked_albums = dict(((path, album_id) for (path, album_id) in db.execute("SELECT path, album_id FROM album;")))

    def scan_album(path_str: str, track_files: list[Path]):
        nonlocal unchecked_albums
        found_tracks = []
        for track_file in sorted(track_files):
            stat = track_file.stat()
            mtime = tools.format_file_timestamp(stat.st_mtime)
            found_tracks.append({"SourceFile": track_file.name, "FileSize": stat.st_size, "FileModifyDate": mtime})
        album_id = unchecked_albums.get(path_str)
        if album_id is None:
            album = tags.with_track_metadata(library_root, {"path": path_str, "tracks": found_tracks})
            logger.info(f"add album {album}")
            database.add(db, album)
            return "added"

        del unchecked_albums[path_str]
        stored_album = database.load_album(db, album_id)
        if track_files_modified(stored_album["tracks"], found_tracks):
            album = tags.with_track_metadata(library_root, stored_album | {"tracks": found_tracks})
            database.update(db, album)
            return "updated"

        return "unchanged"

    stats = {"scanned": 0, "added": 0, "removed": 0, "updated": 0, "unchanged": 0}
    try:
        paths = glob.iglob("**/", root_dir=library_root, recursive=True)
        # preload the list of paths in order to show a progress bar
        paths = tools.progress_bar(list(paths), lambda: " Scan ")  # TODO skip if configured to save memory
        for path_str in paths:
            album_path = library_root / path_str
            logger.debug(f"checking {album_path}")
            track_files = [entry for entry in album_path.iterdir() if entry.is_file() and entry.suffix in TRACK_SUFFIXES]
            stats["scanned"] += 1
            if len(track_files) > 0:
                stats[scan_album(path_str, track_files)] += 1
    except KeyboardInterrupt:
        logger.error("\scan interrupted, exiting")

    # remaining entries in unchecked_albums are apparently no longer in the library
    for album_id in unchecked_albums.values():
        logger.info(f"remove album {album_id}")
        database.remove(db, album_id)
        stats["removed"] += 1

    click.echo(f"scanned {library_root} in {int(time.perf_counter() - start_time)}s. Stats = {stats}")
