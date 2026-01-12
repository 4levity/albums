import click
from collections.abc import Iterator
import humanize
import logging
import os
from pathlib import Path
import shutil
import time
from . import tools


logger = logging.getLogger(__name__)


def do_sync(albums: Iterator[dict], dest: Path, library_root: Path, delete, force):
    existing_dest_paths = set(dest.rglob("*"))
    skipped_tracks = 0
    total_size = 0
    tracks = []
    for album in albums:
        for track in album["tracks"]:
            # remove in-use dirs from destination set if present
            dest_path = dest / Path(album["path"])
            while dest_path.relative_to(dest).name != "":
                if dest_path.exists() and not dest_path.is_dir():
                    logger.error(f"destination {str(dest_path)} exists, but is not a directory. Aborting.")
                    return
                existing_dest_paths.discard(dest_path)
                dest_path = dest_path.parent

            dest_file: Path = dest / album["path"] / track["source_file"]
            if dest_file.exists():
                if not dest_file.is_file():
                    logger.error(f"destination {str(dest_file)} exists, but is not a file. Aborting.")
                    return
                existing_dest_paths.remove(dest_file)
                stat = dest_file.stat()
                # treat last-modified within one second as identical due to rounding errors and file system differences
                different_timestamp = abs(int(stat.st_mtime) - track["modify_timestamp"]) > 1
                copy_track = stat.st_size != track["file_size"] or different_timestamp
                skipped_tracks += 0 if copy_track else 1
            else:
                copy_track = True
            if copy_track:
                total_size += track["file_size"]
                source_file = library_root / album["path"] / track["source_file"]
                tracks.append((source_file, dest_file, track["file_size"]))

    if delete and len(existing_dest_paths) > 0:
        click.echo(f"will delete {len(existing_dest_paths)} paths from {dest}")
        if force or click.confirm("are you sure you want to delete?"):
            click.echo("deleting files from destination")
            for delete_path in sorted(existing_dest_paths, reverse=True):
                if delete_path.is_dir():
                    delete_path.rmdir()
                else:
                    delete_path.unlink()
        else:
            click.echo("skipped deleting files from destination")

    elif len(existing_dest_paths) > 0:
        logger.warning(f"not deleting {len(existing_dest_paths)} paths from {dest}")

    skipped = f"(skipped {skipped_tracks})" if skipped_tracks > 0 else ""
    if len(tracks) > 0:
        click.echo(f"copying {len(tracks)} tracks {humanize.naturalsize(total_size)} to {dest} {skipped}")
        copied_bytes = 0
        start_time = time.perf_counter()

        def get_progress():
            rate = copied_bytes / (max(0.001, time.perf_counter() - start_time))
            mm, ss = divmod((total_size - copied_bytes) / rate, 60) if rate > 0 else (0, 0)
            return f" Copied {humanize.naturalsize(copied_bytes)} ({humanize.naturalsize(rate)}/sec) {int(mm)}:{int(ss):02d} left "

        for track in tools.progress_bar(sorted(tracks, key=lambda t: t[1]), get_progress):
            source_file = track[0]
            dest_file = track[1]
            size = track[2]
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            logger.debug(f"copying to {dest_file}")
            shutil.copy2(source_file, dest_file)
            copied_bytes += size
    else:
        click.echo(f"no tracks to copy {skipped}")
