import click
import glob
import logging
from pathlib import Path
import sqlite3
import time

import albums.database.operations
from ..tools import progress_bar
from .metadata import get_metadata


logger = logging.getLogger(__name__)
DEFAULT_SUPPORTED_FILE_TYPES = [".flac", ".mp3", ".m4a", ".wma", ".ogg"]


def scan(db: sqlite3.Connection, library_root: Path, supported_file_types=DEFAULT_SUPPORTED_FILE_TYPES, path_selector=None, reread=False):
    start_time = time.perf_counter()

    if path_selector is not None:
        stored_paths = path_selector()
    else:
        stored_paths = db.execute("SELECT path, album_id FROM album;")
    unchecked_albums = dict(((path, album_id) for (path, album_id) in stored_paths))

    def scan_album(path_str: str, track_files: list[Path]):
        nonlocal unchecked_albums
        found_tracks = []
        for track_file in sorted(track_files):
            stat = track_file.stat()
            found_tracks.append({"filename": track_file.name, "file_size": stat.st_size, "modify_timestamp": int(stat.st_mtime)})
        album_id = unchecked_albums.get(path_str)
        if album_id is None:
            _load_track_metadata(library_root, path_str, found_tracks)
            album = {"path": path_str, "tracks": found_tracks}
            logger.debug(f"add album {album}")
            albums.database.operations.add(db, album)
            return "added"

        del unchecked_albums[path_str]

        check_for_missing_metadata = True  # TODO add setting to disable for faster scan
        stored_album = albums.database.operations.load_album(db, album_id, check_for_missing_metadata)
        if (
            reread
            or _track_files_modified(stored_album["tracks"], found_tracks)
            or (check_for_missing_metadata and _missing_metadata(stored_album["tracks"]))
        ):
            _load_track_metadata(library_root, path_str, found_tracks)
            albums.database.operations.update_tracks(db, album_id, found_tracks)
            return "updated"

        return "unchanged"

    stats = {"scanned": 0, "added": 0, "removed": 0, "updated": 0, "unchanged": 0}
    track_suffixes = [str.lower(suffix) for suffix in supported_file_types]
    skipped_file_types = {}
    try:
        if path_selector is not None:
            paths = list(unchecked_albums.keys())
        else:
            click.echo(f"finding folders in {library_root}", nl=False)
            paths = glob.iglob("**/", root_dir=library_root, recursive=True)
        preload_paths = True  # TODO add setting to disable progress bar and save memory
        if preload_paths:
            paths = progress_bar(list(paths), lambda: " Scan ")

        for path_str in paths:
            album_path = library_root / path_str
            logger.debug(f"checking {album_path}")
            track_files = []
            for entry in album_path.iterdir() if path_selector is None or album_path.exists() else []:
                suffix = str.lower(entry.suffix)
                if entry.is_file():
                    if suffix in track_suffixes:
                        track_files.append(entry)
                    else:
                        skipped_file_types[suffix] = skipped_file_types.get(suffix, 0) + 1
            stats["scanned"] += 1
            if len(track_files) > 0:
                result = scan_album(path_str, track_files)
                stats[result] += 1

        # remaining entries in unchecked_albums are apparently no longer in the library
        for path, album_id in unchecked_albums.items():
            logger.info(f"remove album {album_id} {path}")
            albums.database.operations.remove(db, album_id)
            stats["removed"] += 1
    except KeyboardInterrupt:
        logger.error("scan interrupted, exiting")

    click.echo(f"scanned {library_root} in {int(time.perf_counter() - start_time)}s. Stats = {stats}")
    logger.info(f"did not scan files with these extensions: {skipped_file_types}")


def _load_track_metadata(library_root: Path, album_path: str, tracks: list[dict]):
    for track in tracks:
        path = library_root / album_path / track["filename"]
        (tags, stream_info) = get_metadata(path)
        if tags is not None:
            track["tags"] = tags
        else:
            logger.warning(f"couldn't read tags for {path}")
        if stream_info is not None:
            track["stream"] = stream_info
        else:
            logger.warning(f"couldn't read stream info for {path}")


def _track_files_modified(tracks1: list[dict], tracks2: list[dict]):
    if len(tracks1) != len(tracks2):
        return True
    for index, t1 in enumerate(tracks1):
        t2 = tracks2[index]
        if t1["filename"] != t2["filename"] or t1["file_size"] != t2["file_size"] or t1["modify_timestamp"] != t2["modify_timestamp"]:
            return True
    return False


def _missing_metadata(tracks: list[dict]):
    for track in tracks:
        if track["tags"] == {} or track["stream"] == {}:
            return True
    return False
