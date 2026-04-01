import logging
import os
import shutil
from pathlib import Path
from typing import Sequence, Tuple

import humanize
from prompt_toolkit.shortcuts import confirm
from rich.markup import escape
from rich.progress import Progress, TransferSpeedColumn
from sqlalchemy.orm import Session

from albums.database import selector

from ..app import Context
from ..config import SyncDestination
from ..library.paths import make_template_path
from ..words.make import plural

logger = logging.getLogger(__name__)


def do_sync(ctx: Context, dest: SyncDestination, delete: bool, force: bool):
    if not ctx.db or str(ctx.config.library) in {"", "."}:
        raise ValueError("do_sync called without db connection + library")

    existing_dest_paths = set(dest.path_root.rglob("*"))
    skipped_tracks = 0
    total_size = 0
    tracks: list[tuple[Path, Path, int]] = []  # list of (source, destination, size)
    with Session(ctx.db) as session:
        if dest.collection:
            source_albums = selector.load_album_entities(session, regex=False, collection=[dest.collection])
        else:
            source_albums = ctx.select_album_entities(session)
        for album in source_albums:
            dest_relpath = make_template_path(ctx, album, dest.relpath_template_artist, dest.relpath_template_compilation)
            dest_path = dest.path_root / (dest_relpath if dest_relpath else album.path)
            logger.info(f"copy {escape(Path(album.path).name)} to {dest_path}")
            for track in sorted(album.tracks):
                # remove in-use dirs from destination set if present
                tmp_dest_path = dest_path
                while tmp_dest_path.relative_to(dest.path_root).name != "":
                    if tmp_dest_path.exists() and not tmp_dest_path.is_dir():
                        logger.error(f"destination {str(tmp_dest_path)} exists, but is not a directory. Aborting.")
                        return
                    existing_dest_paths.discard(tmp_dest_path)
                    tmp_dest_path = tmp_dest_path.parent

                dest_track_path: Path = dest_path / track.filename
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
        if force or confirm("are you sure you want to delete?"):
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
        ctx.console.print(
            f"[bold green]not deleting {plural(existing_dest_paths, 'path')} from {escape(str(dest))}, e.g. {list(existing_dest_paths)[:2]}"
        )

    skipped = f" (skipped {skipped_tracks})" if skipped_tracks > 0 else ""
    if len(tracks) > 0:
        ctx.console.print(f"Destination: {escape(str(dest))} {skipped}")
        copy_files_with_progress(ctx, tracks)
    else:
        ctx.console.print(f"no tracks to copy{skipped}")


def copy_files_with_progress(ctx: Context, to_copy: Sequence[Tuple[Path, Path, int]]):
    total_size = sum(size for _src, _dest, size in to_copy)
    ctx.console.print(f"Copying {plural(to_copy, 'file')} {humanize.naturalsize(total_size)}")
    with Progress(*Progress.get_default_columns(), TransferSpeedColumn()) as progress:
        sync_task = progress.add_task("Progress", total=total_size)
        for source_track_path, dest_track_path, size in sorted(to_copy, key=lambda t: t[1]):
            os.makedirs(os.path.dirname(dest_track_path), exist_ok=True)
            logger.debug(f"copying to {dest_track_path}")
            shutil.copy2(source_track_path, dest_track_path)
            progress.update(sync_task, advance=size)
    ctx.console.print("Done copying")
