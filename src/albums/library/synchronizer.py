import click
from collections.abc import Iterator
import humanize
import logging
import os
from pathlib import Path
import shutil
import time

from ..tools import progress_bar
from ..types import Album


logger = logging.getLogger(__name__)


def do_sync(albums: Iterator[Album], dest: Path, library_root: Path, delete, force):
    existing_dest_paths = set(dest.rglob("*"))
    skipped_tracks = 0
    total_size = 0
    tracks = []
    for album in albums:
        for track in album.tracks:
            # remove in-use dirs from destination set if present
            dest_path = dest / Path(album.path)
            while dest_path.relative_to(dest).name != "":
                if dest_path.exists() and not dest_path.is_dir():
                    logger.error(f"destination {str(dest_path)} exists, but is not a directory. Aborting.")
                    return
                existing_dest_paths.discard(dest_path)
                dest_path = dest_path.parent

            dest_track_path: Path = dest / album.path / track.filename
            if dest_track_path.exists():
                if not dest_track_path.is_file():
                    logger.error(f"destination {str(dest_track_path)} exists, but is not a file. Aborting.")
                    return
                existing_dest_paths.remove(dest_track_path)
                stat = dest_track_path.stat()
                # treat last-modified within one second as identical due to rounding errors and file system differences
                different_timestamp = abs(int(stat.st_mtime) - track.modify_timestamp) > 1
                copy_track = stat.st_size != track.file_size or different_timestamp
                skipped_tracks += 0 if copy_track else 1
            else:
                copy_track = True
            if copy_track:
                total_size += track.file_size
                source_track_path = library_root / album.path / track.filename
                tracks.append((source_track_path, dest_track_path, track.file_size))

    if delete and len(existing_dest_paths) > 0:
        click.echo(f"will delete {len(existing_dest_paths)} paths from {dest}")
        if force or click.confirm("are you sure you want to delete?"):
            click.echo("deleting files from destination")
            for delete_path in sorted(existing_dest_paths, reverse=True):
                if delete_path.is_dir():
                    delete_path.rmdir()
                else:
                    delete_path.unlink()
                logger.info(f"deleting {delete_path}")
        else:
            click.echo("skipped deleting files from destination")

    elif len(existing_dest_paths) > 0:
        logger.warning(f"not deleting {len(existing_dest_paths)} paths from {dest}: {list(existing_dest_paths)[:2]}")

    skipped = f"(skipped {skipped_tracks})" if skipped_tracks > 0 else ""
    if len(tracks) > 0:
        click.echo(f"copying {len(tracks)} tracks {humanize.naturalsize(total_size)} to {dest} {skipped}")
        copied_bytes = 0
        start_time = time.perf_counter()

        def get_progress():
            rate = copied_bytes / (max(0.001, time.perf_counter() - start_time))
            mm, ss = divmod((total_size - copied_bytes) / rate, 60) if rate > 0 else (0, 0)
            return f" Copied {humanize.naturalsize(copied_bytes)} ({humanize.naturalsize(rate)}/sec) {int(mm)}:{int(ss):02d} left "

        for source_track_path, dest_track_path, size in progress_bar(sorted(tracks, key=lambda t: t[1]), get_progress):
            os.makedirs(os.path.dirname(dest_track_path), exist_ok=True)
            logger.debug(f"copying to {dest_track_path}")
            shutil.copy2(source_track_path, dest_track_path)
            copied_bytes += size
    else:
        click.echo(f"no tracks to copy {skipped}")
