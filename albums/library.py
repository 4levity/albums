import glob
import logging
from pathlib import Path
import sqlite3
import time

import click
from albums import database
from albums import tags
from albums import tools


logger = logging.getLogger(__name__)
TRACK_SUFFIXES = [".flac", ".mp3", ".m4a"]


def fast_scan(scan_albums: dict, library_root: Path, album_path: Path, subalbum_depth=0):
    scan_path = str(album_path.relative_to(library_root))
    if scan_path in scan_albums:
        return

    album = {"path": scan_path, "tracks": []}
    track_files: list[Path] = []
    for entry in album_path.iterdir():
        if entry.is_file() and entry.suffix in TRACK_SUFFIXES:
            track_files.append(entry)
        elif subalbum_depth > 0 and entry.is_dir():
            fast_scan(scan_albums, library_root, entry, subalbum_depth - 1)

    if len(track_files) > 0:
        for track_file in sorted(track_files):
            stat = track_file.stat()
            mtime = tools.format_file_timestamp(stat.st_mtime)
            album["tracks"].append({"SourceFile": track_file.name, "FileSize": stat.st_size, "FileModifyDate": mtime})
        scan_albums[album["path"]] = album


def tracks_changed(album1: dict, album2: dict):
    tracks1: list[dict] = album1["tracks"]
    tracks2: list[dict] = album2["tracks"]

    if len(tracks1) != len(tracks2):
        return True
    for index, t1 in enumerate(tracks1):
        t2 = tracks2[index]
        if t1["SourceFile"] != t2["SourceFile"] or t1["FileSize"] != t2["FileSize"] or t1["FileModifyDate"] != t2["FileModifyDate"]:
            return True
    return False


def has_metadata(album: dict):
    for track in album["tracks"]:
        if "FileType" not in track:
            return False
    return True


def find_paths_in_library(library_root: Path, glob_specs: list[str]):
    album_paths: list[Path] = []
    for glob_spec in glob_specs:
        click.echo(f"searching {library_root / glob_spec}\r", nl=False)
        for path_str in glob.iglob(glob_spec, root_dir=library_root, recursive=True):
            full_path = library_root / path_str
            if full_path.is_dir():
                album_paths.append(full_path)
    return album_paths


@click.command(help="scan and update database")
@click.option("--known-only", is_flag=True, help="only scan previously-scanned folders")
@click.pass_context
def scan(ctx: click.Context, known_only):
    if ctx.obj.get("SCAN_DONE", False):
        logger.info("scan already done, not scanning again")
        return

    start_time = time.perf_counter()

    db: sqlite3.Connection = ctx.obj["DB_CONNECTION"]
    albums: dict = ctx.obj["ALBUMS_CACHE"]
    library_root: Path = ctx.obj["LIBRARY_ROOT"]
    locations = ctx.obj["CONFIG"].get("locations", {})

    if known_only:
        album_paths = [Path(library_root / p) for p in albums.keys()]
        subalbum_depth = 0
        logger.info(f"rescanning {len(album_paths)} known album folders")
    else:
        glob_specs = (locations["albums"] if "albums" in locations else "**").split("|")
        album_paths = find_paths_in_library(library_root, glob_specs)
        subalbum_depth = int(ctx.obj["CONFIG"].get("locations", {}).get("subalbum_depth", 0))
        logger.info(f"scanning {len(album_paths)} dirs for albums")

    scan_albums = {}
    for album_path in tools.progress_bar(sorted(album_paths), lambda: " Scanning "):
        logger.debug(f"scanning for albums at {album_path}")
        fast_scan(scan_albums, library_root, album_path, subalbum_depth)
    logger.info(f"Scanned library {library_root} in {int(time.perf_counter() - start_time)} seconds.")

    albums_to_remove: list[str] = []
    changed_albums: list[dict] = []
    missing_metadata_albums: list[str] = []
    unchanged = 0
    for album in albums.values():
        if album["path"] in scan_albums:
            rescanned_album = scan_albums[album["path"]]
            if tracks_changed(album, rescanned_album):
                changed_albums.append(rescanned_album)
            elif not has_metadata(album):
                missing_metadata_albums.append(album["path"])
            else:
                unchanged += 1
        else:
            albums_to_remove.append(album["path"])
    new_albums: list[dict] = [scan_album for scan_album in scan_albums.values() if scan_album["path"] not in albums]

    # remove albums
    for remove_album_path in albums_to_remove:
        logger.info(f"remove album {remove_album_path}")
        del albums[remove_album_path]
        database.remove(db, remove_album_path)

    # add albums
    for new_album in new_albums:
        logger.info(f"add album {new_album}")
        albums[new_album["path"]] = new_album
        database.add(db, new_album)

    # replace track data on changed albums
    for changes in changed_albums:
        albums[changes["path"]] |= changes
        database.update(db, albums[changes["path"]])

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
                albums[album_path] = tags.with_track_metadata(library_root, albums[album_path])
                database.update(db, albums[album_path])
        except KeyboardInterrupt:
            logger.error("\nloading interrupted, exiting")
        logger.info(f"Updated track metadata in {int(time.perf_counter() - start_time)} seconds.")
