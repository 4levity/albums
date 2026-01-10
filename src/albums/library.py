import glob
import logging
import os
from pathlib import Path
import sqlite3
import time

import click
from albums import database
from albums import tags
from albums import tools


logger = logging.getLogger(__name__)
TRACK_SUFFIXES = [".flac", ".mp3", ".m4a"]


def fast_scan(library_root: Path, album_path: Path, subalbum_depth=0, scanned_folders: set[str] = set()):
    """
    Scan a folder for an album.

    :param library_root: Description
    :type library_root: Path
    :param album_path: Description
    :type album_path: Path
    :param subalbum_depth: Search depth for subfolders with more albums, default 0 disables
    :param scanned_folders: Folders to skip. Every folder examined will be added to this set.
    :type scanned_folders: set[str]
    """
    scan_path = str(album_path.relative_to(library_root))
    if scan_path in scanned_folders:
        return {}
    scanned_folders.add(scan_path)
    # if not album_path.exists() or not album_path.is_dir():
    #     return {}

    album = {"path": str(album_path.relative_to(library_root)), "tracks": []}
    track_files: list[Path] = []
    albums = {}
    for entry in album_path.iterdir():
        if entry.is_file() and entry.suffix in TRACK_SUFFIXES:
            track_files.append(entry)
        elif subalbum_depth > 0 and entry.is_dir():
            albums |= fast_scan(library_root, entry, subalbum_depth - 1, scanned_folders)

    if len(track_files) > 0:
        for track_file in sorted(track_files):
            stat = track_file.stat()
            mtime = tools.format_file_timestamp(stat.st_mtime)
            album["tracks"].append({"SourceFile": track_file.name, "FileSize": stat.st_size, "FileModifyDate": mtime})
        albums[album["path"]] = album
    return albums


def track_files_modified(tracks1: list[dict], tracks2: list[dict]):
    if len(tracks1) != len(tracks2):
        return True
    for index, t1 in enumerate(tracks1):
        t2 = tracks2[index]
        if t1["SourceFile"] != t2["SourceFile"] or t1["FileSize"] != t2["FileSize"] or t1["FileModifyDate"] != t2["FileModifyDate"]:
            return True
    return False


def has_metadata(tracks: list[dict]):
    for track in tracks:
        if "FileType" not in track:
            return False
    return True


def is_dir(path: Path):
    return path.exists() and path.is_dir()


def scan(db: sqlite3.Connection, albums_cache: dict, library_root: Path, locations: list[str], known_only: bool):
    start_time = time.perf_counter()

    if known_only:
        album_paths = [path for (path,) in db.execute("SELECT path FROM album;") if is_dir(library_root / path)]
        subalbum_depth = 0
        logger.info(f"rescanning {len(album_paths)} known album folders")
    else:
        glob_specs = (locations["albums"] if "albums" in locations else "**/").split("|")
        # album_paths = find_paths_in_library(library_root, glob_specs)
        album_paths: list[str] = []
        for glob_spec in glob_specs:
            click.echo(f"searching {library_root}{os.sep}{glob_spec}\033[K\r", nl=False)
            for path_str in glob.iglob(glob_spec, root_dir=library_root, recursive=True):
                full_path = library_root / path_str
                if full_path.is_dir():
                    album_paths.append(path_str)
        click.echo("\033[K", nl=False)
        subalbum_depth = int(locations.get("subalbum_depth", 0))
        logger.info(f"scanning {len(album_paths)} dirs for albums")

    scanned_albums = {}
    scanned_paths = set()
    for album_path_str in tools.progress_bar(sorted(album_paths), lambda: " Scanning "):
        album_path = library_root / album_path_str
        logger.debug(f"scanning for albums at {album_path}")
        scanned_albums |= fast_scan(library_root, album_path, subalbum_depth, scanned_paths)
    logger.info(f"Scanned library {library_root} in {int(time.perf_counter() - start_time)} seconds.")

    start_time = time.perf_counter()
    albums_to_remove: list[str] = []
    changed_albums: list[dict] = []
    missing_metadata_albums: list[str] = []
    unchanged = 0
    for album_id, path in db.execute("SELECT album_id, path FROM album;"):
        if path in scanned_albums:
            rescanned_album = scanned_albums[path]
            stored_tracks = database.load_tracks(db, album_id)
            if track_files_modified(stored_tracks, rescanned_album["tracks"]):
                changed_albums.append(rescanned_album)
            elif not has_metadata(stored_tracks):
                missing_metadata_albums.append(path)
            else:
                unchanged += 1
        else:
            albums_to_remove.append(path)
    logger.info(f"Checked metadata in {int(time.perf_counter() - start_time)} seconds.")

    new_albums: list[dict] = [scan_album for scan_album in scanned_albums.values() if scan_album["path"] not in albums_cache]

    # remove albums
    for remove_album_path in albums_to_remove:
        logger.info(f"remove album {remove_album_path}")
        del albums_cache[remove_album_path]
        database.remove(db, remove_album_path)

    # add albums
    for new_album in new_albums:
        logger.info(f"add album {new_album}")
        albums_cache[new_album["path"]] = new_album
        database.add(db, new_album)

    # replace track data on changed albums
    for changes in changed_albums:
        albums_cache[changes["path"]] |= changes
        database.update(db, albums_cache[changes["path"]])

    logger.info(
        f"Albums removed = {len(albums_to_remove)} / added = {len(new_albums)} / changed = {len(changed_albums)} / unchanged = {unchanged} / missing-metadata = {len(missing_metadata_albums)}"
    )

    albums_needing_metadata_paths = (
        [album["path"] for album in changed_albums if len(album["tracks"]) > 0]
        + missing_metadata_albums
        + [album["path"] for album in new_albums if len(album["tracks"]) > 0]
    )
    if len(albums_needing_metadata_paths) > 0:
        click.echo(f"Loading metadata for {len(albums_needing_metadata_paths)} albums using {tags.check_metadata_tool()}")
        start_time = time.perf_counter()
        try:  # this may take a long time, save progress if interrupted
            for album_path in tools.progress_bar(albums_needing_metadata_paths, lambda: " Loading "):
                albums_cache[album_path] = tags.with_track_metadata(library_root, albums_cache[album_path])
                database.update(db, albums_cache[album_path])
        except KeyboardInterrupt:
            logger.error("\nloading interrupted, exiting")
        logger.info(f"Updated track metadata in {int(time.perf_counter() - start_time)} seconds.")
