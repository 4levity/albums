import click
import glob
import logging
from pathlib import Path
import sqlite3
import time
import albums.database.operations
from ..tools import progress_bar, get_metadata


logger = logging.getLogger(__name__)
TRACK_SUFFIXES = [".flac", ".mp3", ".m4a"]


def track_files_modified(tracks1: list[dict], tracks2: list[dict]):
    if len(tracks1) != len(tracks2):
        return True
    for index, t1 in enumerate(tracks1):
        t2 = tracks2[index]
        if t1["source_file"] != t2["source_file"] or t1["file_size"] != t2["file_size"] or t1["modify_timestamp"] != t2["modify_timestamp"]:
            return True
    return False


def missing_metadata(tracks: list[dict]):
    for track in tracks:
        if track["metadata"] == {}:
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
            found_tracks.append({"source_file": track_file.name, "file_size": stat.st_size, "modify_timestamp": int(stat.st_mtime)})
        album_id = unchecked_albums.get(path_str)
        if album_id is None:
            load_track_metadata(library_root, path_str, found_tracks)
            album = {"path": path_str, "tracks": found_tracks}
            logger.debug(f"add album {album}")
            albums.database.operations.add(db, album)
            return "added"

        del unchecked_albums[path_str]

        check_for_missing_metadata = True  # TODO add setting to disable for faster scan
        stored_album = albums.database.operations.load_album(db, album_id, check_for_missing_metadata)
        modified = track_files_modified(stored_album["tracks"], found_tracks)
        if modified or (check_for_missing_metadata and missing_metadata(stored_album["tracks"])):
            load_track_metadata(library_root, path_str, found_tracks)
            albums.database.operations.update_tracks(db, album_id, found_tracks)
            return "updated"

        return "unchanged"

    stats = {"scanned": 0, "added": 0, "removed": 0, "updated": 0, "unchanged": 0}
    try:
        paths = glob.iglob("**/", root_dir=library_root, recursive=True)
        # preload the list of paths in order to show a progress bar
        click.echo(f"finding folders in {library_root}", nl=False)
        paths = progress_bar(list(paths), lambda: " Scan ")  # TODO add setting to disable progress bar and save memory
        for path_str in paths:
            album_path = library_root / path_str
            logger.debug(f"checking {album_path}")
            track_files = [entry for entry in album_path.iterdir() if entry.is_file() and str.lower(entry.suffix) in TRACK_SUFFIXES]
            stats["scanned"] += 1
            if len(track_files) > 0:
                result = scan_album(path_str, track_files)
                stats[result] += 1

        # remaining entries in unchecked_albums are apparently no longer in the library
        for album_id in unchecked_albums.values():
            logger.info(f"remove album {album_id}")
            stats["removed"] += 1
    except KeyboardInterrupt:
        logger.error("\scan interrupted, exiting")

    click.echo(f"scanned {library_root} in {int(time.perf_counter() - start_time)}s. Stats = {stats}")


def load_track_metadata(library_root: Path, album_path: str, tracks: list[dict]):
    metadata = get_metadata(library_root / album_path, [track["source_file"] for track in tracks])
    if len(tracks) == len(metadata):
        for index, track in enumerate(tracks):
            if track["source_file"] == metadata[index]["SourceFile"]:
                del metadata[index]["SourceFile"]
                tracks[index]["metadata"] = metadata[index]
            else:
                logger.warning(
                    f"track metadata out of order at index {index}: {track['source_file']} != {metadata[index]['source_file']} -- in album {album_path}"
                )
    else:
        logger.warning(f"track count {len(tracks)} does not match metadata count {len(metadata)} for album {album_path}")
