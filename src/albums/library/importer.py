import glob
import logging
import os
import shutil
from itertools import chain
from pathlib import Path
from typing import Sequence, Tuple

import humanize
from prompt_toolkit import choice
from prompt_toolkit.shortcuts import confirm
from rich.markup import escape
from rich.progress import Progress, TransferSpeedColumn
from sqlalchemy.orm import Session

from ..app import Context
from ..checks.checker import Checker
from ..library.duplicates import DuplicateFinder, album_in_library
from ..library.paths import make_template_paths
from ..library.scanner import scan
from ..types import Album
from ..words.make import plural

logger = logging.getLogger(__name__)


class Importer:
    ctx: Context
    _parent_context: Context
    _library: Path
    _extra: bool
    _recursive: bool
    _automatic: bool
    _duplicate_finder = DuplicateFinder()

    def __init__(self, child_context: Context, extra: bool, recursive: bool, automatic: bool):
        if child_context.parent is None:
            raise RuntimeError("Importer must be created in child context")

        self.ctx = child_context
        self._parent_context = child_context.parent
        self._library = child_context.config.library
        self._extra = extra
        self._recursive = recursive
        self._automatic = automatic

    def scan(self):
        (albums_total, _) = scan(self.ctx, check_first_full_scan_path_count=lambda ct: self._check_path_count(ct))
        if albums_total == 0:
            self.ctx.console.print(f"Album not found at {escape(str(self.ctx.config.library))}")
            raise SystemExit(1)
        if albums_total > 1 and self._recursive:
            self.ctx.console.print(
                f"THe [bold]--recursive[/bold] option cannot be used because there is more than one album at {escape(str(self.ctx.config.library))}"
            )
            raise SystemExit(1)
        with self.ctx.console.status("Initializing duplicate album finder", spinner="bouncingBar"):
            with Session(self._parent_context.db) as session:
                self._duplicate_finder.start(session)
        return albums_total

    def run(self):
        checker = Checker(self.ctx, self._automatic, preview=False, fix=False, interactive=True, show_ignore_option=True)
        non_interactive_checker = Checker(self.ctx, False, False, False, False, False)
        with Session(self.ctx.db) as session:
            for album in self.ctx.select_album_entities(session):
                (exists, ok) = self._check_existing_destination(album, self._make_library_paths(album))
                if not ok:
                    continue
                issues = 0
                quit = False
                self.ctx.select_album_entities = lambda _: iter([album])
                self.ctx.console.print(f"Starting import: {escape(album.path)}", highlight=False)
                while not quit and checker.run_enabled(session):
                    self.ctx.console.print("Remaining issues:")
                    issues = non_interactive_checker.run_enabled(session)
                    if issues == 0:
                        self.ctx.console.print("No issues")
                    quit = issues == 0 or confirm("There are still issues. Do you want to skip importing this album?")

                if not issues:
                    library_paths = self._make_library_paths(album)
                    if not exists:  # check again in case tag fixes changed the destination paths
                        (exists, ok) = self._check_existing_destination(album, library_paths)
                        if not ok:
                            continue
                    source_path = self.ctx.config.library / album.path
                    if self._automatic:
                        path_in_library = library_paths[0]
                    else:
                        options = [(album_path, f">> Copy to: {album_path}") for album_path in library_paths] + [("", ">> Cancel")]
                        path_in_library = choice(message=f"Ready to copy from {source_path}", options=options)
                    if path_in_library:
                        self.ctx.console.print(f"Import album from {source_path} to {str(self.ctx.config.library / path_in_library)}")
                        self.import_album(source_path, path_in_library, album)

    def _make_library_paths(self, album: Album):
        return make_template_paths(
            self.ctx, album, self.ctx.config.default_import_path, self.ctx.config.default_import_path_various, self.ctx.config.more_import_paths
        )

    def _check_existing_destination(self, album: Album, library_paths: Sequence[str]) -> Tuple[bool, bool]:
        # TODO check for duplicate album by tag values too
        existing = next((path for path in library_paths if (self._parent_context.config.library / path).exists()), None)
        if existing is None:
            existing = album_in_library(self.ctx, album)

        if existing is not None:
            self.ctx.console.print(f"This album appears to be in the library: [bold]{escape(existing)}[/bold]")
            if not self._automatic and confirm("Do you want to add it anyway?"):
                return (True, True)
            else:
                self.ctx.console.print("Skipping import")
                return (True, False)
        return (False, True)

    def _check_path_count(self, path_count: int) -> None:
        if path_count > self.ctx.config.import_scan_max_paths:
            self.ctx.console.print(
                f"found {path_count} paths, but import command is limited to {self.ctx.config.import_scan_max_paths} (controlled by global setting [bold]import_scan_max_paths[/bold])"
            )
            raise SystemExit(1)

    def import_album(self, source_path: Path, destination_path_in_library: str, album: Album):
        src = source_path.resolve()
        if not src.is_dir():
            logger.error(f"import_album: not a directory: {str(src)}")
            raise SystemExit(1)

        destination_path = self._parent_context.config.library / destination_path_in_library
        dest = Path(destination_path).resolve()
        if dest.exists():
            logger.error(f"import_album: destination already exists: {str(dest)}")
            raise SystemExit(1)
        if self._extra or self._recursive:
            filenames = glob.iglob("**", root_dir=src, recursive=self._recursive)
        else:
            filenames = chain((track.filename for track in sorted(album.tracks)), (file.filename for file in sorted(album.picture_files)))

        to_copy: list[tuple[Path, Path, int]] = []  # list of (source, destination, size)
        total_size = 0
        for filename in filenames:
            src_path = src / filename
            if src_path.is_file():
                size = src_path.stat().st_size
                total_size += size
                to_copy.append((src_path, dest / filename, size))
        if not to_copy:
            raise RuntimeError("unexpected: no files to copy?")

        self.ctx.console.print(f"Copying {plural(to_copy, 'file')} {humanize.naturalsize(total_size)}")
        os.makedirs(dest, exist_ok=True)
        with Progress(*Progress.get_default_columns(), TransferSpeedColumn()) as progress:
            sync_task = progress.add_task("Progress", total=total_size)
            for source_track_path, dest_track_path, size in sorted(to_copy, key=lambda t: t[1]):
                if self._recursive:
                    os.makedirs(os.path.dirname(dest_track_path), exist_ok=True)
                logger.debug(f"copying to {dest_track_path}")
                shutil.copy2(source_track_path, dest_track_path)
                progress.update(sync_task, advance=size)

        self.ctx.console.print(f"Imported album to {escape(destination_path_in_library)} (will be added to library on next scan)")
        # TODO add album to database immediately + include cover source mark or ignored checks from import process
