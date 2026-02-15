import logging
import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import humanize
from rich.markup import escape
from rich.progress import Progress, TransferSpeedColumn
from rich.prompt import Confirm

from .. import app
from ..types import Album

logger = logging.getLogger(__name__)


def do_sync(ctx: app.Context, albums: Iterator[Album], dest: Path, delete: bool, force: bool):
    if not ctx.db or str(ctx.config.library) in {"", "."}:
        raise ValueError("do_sync called without db connection + library")

    existing_dest_paths = set(dest.rglob("*"))
    skipped_tracks = 0
    total_size = 0
    tracks: list[tuple[Path, Path, int]] = []  # list of (source, destination, size)
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
                source_track_path = ctx.config.library / album.path / track.filename
                tracks.append((source_track_path, dest_track_path, track.file_size))

    if delete and len(existing_dest_paths) > 0:
        ctx.console.print(f"[orange]will delete {len(existing_dest_paths)} paths from {escape(str(dest))}")
        if force or Confirm.ask("are you sure you want to delete?", default=False, console=ctx.console):
            ctx.console.print("[bold red]deleting files from destination")
            for delete_path in sorted(existing_dest_paths, reverse=True):
                if delete_path.is_dir():
                    delete_path.rmdir()
                else:
                    delete_path.unlink()
                logger.info(f"deleting {delete_path}")
            ctx.console.print("done deleting files.")
        else:
            ctx.console.print("skipped deleting files from destination")

    elif len(existing_dest_paths) > 0:
        ctx.console.print(f"[bold green]not deleting {len(existing_dest_paths)} paths from {escape(str(dest))}, e.g. {list(existing_dest_paths)[:2]}")

    skipped = f" (skipped {skipped_tracks})" if skipped_tracks > 0 else ""
    if len(tracks) > 0:
        ctx.console.print(f"copying {len(tracks)} tracks {humanize.naturalsize(total_size)} to {escape(str(dest))} {skipped}")

        with Progress(*Progress.get_default_columns(), TransferSpeedColumn()) as progress:
            sync_task = progress.add_task("Progress", total=total_size)
            for source_track_path, dest_track_path, size in sorted(tracks, key=lambda t: t[1]):
                os.makedirs(os.path.dirname(dest_track_path), exist_ok=True)
                logger.debug(f"copying to {dest_track_path}")
                shutil.copy2(source_track_path, dest_track_path)
                progress.update(sync_task, advance=size)

        ctx.console.print("done copying.")

    else:
        ctx.console.print(f"no tracks to copy{skipped}")
