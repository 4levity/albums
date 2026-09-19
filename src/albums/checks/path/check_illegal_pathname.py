import logging
import os
from os import rename, sep
from pathlib import Path
from typing import Final

from pathvalidate import ValidationError, sanitize_filename, validate_filename
from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.entities import Album
from albums.words import pluralize

logger: Final = logging.getLogger(__name__)


class CheckIllegalPathname(Check):
    """Check that filenames and every element of the album path have no invalid characters or reserved names.

    Sanitizing track and picture filenames, and renaming the album folder itself, is offered as an
    automatic fix. A target name that would collide case-insensitively with an entry that already
    exists (a file in the album folder, or a sibling folder) gets a number appended to resolve the
    collision. The file system is checked for such collisions when the preview table is rendered and
    again when the fix runs, because entries may change in between.

    An illegal name in a parent folder of the album folder cannot be fixed automatically, because
    renaming a parent folder would move every album beneath it: the check fails without a fix and
    recommends renaming the folder manually and running a full scan afterwards.
    """

    name = "illegal-pathname"
    default_config = {"enabled": True}

    def check(self, album: Album):
        issues: set[str] = set()
        for track in album.tracks:
            issues = issues.union(self._check(track.filename))
        for picture_file in album.picture_files:
            issues = issues.union(self._check(picture_file.filename))

        elements = [segment for segment in album.path.split(sep) if segment]
        bad_parent_folders = [element for element in elements[:-1] if self._needs_sanitizing(element)]
        album_folder = Path(album.path).name
        bad_album_folder = bool(album_folder) and self._needs_sanitizing(album_folder)

        if not issues and not bad_parent_folders and not bad_album_folder:
            return None

        if bad_parent_folders:
            # renaming a parent folder would move every album beneath it, so no automatic fix is possible
            names = ", ".join(f'"{element}"' for element in bad_parent_folders)
            return CheckResult(
                f"illegal {pluralize('folder name', bad_parent_folders)} in album path: {names} (no automatic fix: rename manually, then run a full scan)"
            )

        message_parts: list[str] = []
        if issues:
            message_parts.append(f"illegal {pluralize('filename', issues)}: {', '.join(sorted(issues))}")
        if bad_album_folder:
            message_parts.append(f'illegal folder name: "{album_folder}" (should be "{self._sanitize(album_folder)}")')

        option_parts: list[str] = []
        if issues:
            option_parts.append("all filenames")
        if bad_album_folder:
            option_parts.append("the folder name")
        options = [f">> Sanitize {' and '.join(option_parts)}"]
        option_automatic_index = 0

        # rows are deferred so the file system is checked for name collisions when the table is actually rendered
        table = (
            ["Filename", "New Filename"],
            lambda: self._table_rows(album, bad_album_folder),
        )
        return CheckResult(
            "; ".join(message_parts),
            Fixer(lambda _: self._fix(album), options, False, option_automatic_index, table),
        )

    def _album_filenames(self, album: Album) -> list[str]:
        """Filenames of all album files this check inspects and sanitizes: audio tracks and picture files."""
        return [track.filename for track in album.tracks] + [picture_file.filename for picture_file in album.picture_files]

    def _table_rows(self, album: Album, include_folder: bool) -> list[list[str]]:
        renames = self._new_filename_map(album)
        rows = (
            [
                [
                    escape(filename),
                    f"[yellow]{escape(renames[filename])}[/yellow]" if filename in renames else "[bold italic]no change[/bold italic]",
                ]
                for filename in self._album_filenames(album)
            ]
            if renames
            else []
        )
        if include_folder:
            folder = Path(album.path).name
            if folder and self._needs_sanitizing(folder):
                rows.append([escape(folder + sep), f"[yellow]{escape(self._new_folder_name(album) + sep)}[/yellow]"])
        return rows

    def _check(self, filename: str) -> set[str]:
        try:
            validate_filename(filename, platform=self.ctx.config.path_compatibility)
            return set()
        except ValidationError as ex:
            return {f"{repr(ex)}"}

    def _sanitize(self, name: str) -> str:
        return sanitize_filename(name, replacement_text=self.ctx.config.path_replace_invalid, platform=self.ctx.config.path_compatibility)

    def _needs_sanitizing(self, name: str) -> bool:
        return self._sanitize(name) != name

    def _new_filename_map(self, album: Album) -> dict[str, str]:
        """Map each album file that needs sanitizing to a new name, checked against the file system.

        A target that would collide case-insensitively with an entry that already exists in the album
        folder, or with another name assigned here, gets a number appended before the file extension.
        """
        existing = {str.casefold(entry.name) for entry in (self.ctx.config.library / album.path).iterdir()}
        renames: dict[str, str] = {}
        for filename in self._album_filenames(album):
            base = self._sanitize(filename)
            if base == filename:
                continue
            (stem, suffix) = os.path.splitext(base)
            candidate = base
            num = 0
            while str.casefold(candidate) in existing or str.casefold(candidate) in renames.values():
                num += 1
                candidate = f"{stem} {num}{suffix}"
            renames[filename] = candidate
        return renames

    def _new_folder_name(self, album: Album) -> str:
        """The name to rename the album folder to, checked against the file system: its sanitized name,
        with a number appended if needed so it does not collide case-insensitively with a sibling folder."""
        folder = Path(album.path).name
        base = self._sanitize(folder)
        siblings = {str.casefold(entry.name) for entry in (self.ctx.config.library / album.path).parent.iterdir() if entry.name != folder}
        candidate = base
        num = 0
        while str.casefold(candidate) in siblings:
            num += 1
            candidate = f"{base} {num}"
        return candidate

    def _fix(self, album: Album):
        changed = False
        for filename, new_filename in self._new_filename_map(album).items():
            self.ctx.console.print(f"Renaming {escape(filename)} to {escape(new_filename)}")
            rename(self.ctx.config.library / album.path / filename, self.ctx.config.library / album.path / new_filename)
            changed = True

        album_folder = Path(album.path).name
        if album_folder and self._needs_sanitizing(album_folder):
            # re-check sibling folders on disk: they may have changed since the fix was offered
            new_folder = self._new_folder_name(album)
            new_path_str = str(Path(album.path).parent / new_folder) + sep
            old_path = self.ctx.config.library / album.path
            self.ctx.console.print(f'Renaming folder "{escape(album.path)}" to "{escape(new_path_str)}"', highlight=False)
            rename(old_path, self.ctx.config.library / new_path_str)
            album.path = new_path_str
            changed = True
        return FixResult.of(changed)
