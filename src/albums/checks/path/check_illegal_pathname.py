import logging
from os import rename
from typing import Final

from pathvalidate import ValidationError, sanitize_filename, validate_filename
from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.entities import Album
from albums.words import pluralize

logger: Final = logging.getLogger(__name__)


class CheckIllegalPathname(Check):
    name = "illegal-pathname"
    default_config = {"enabled": True}

    def check(self, album: Album):
        issues: set[str] = set()
        for track in album.tracks:
            issues = issues.union(self._check(track.filename))
        for picture_file in album.picture_files:
            issues = issues.union(self._check(picture_file.filename))

        # TODO also check album.path

        if issues:
            options = [">> Sanitize all filenames"]
            option_automatic_index = 0
            table = (
                ["Filename", "New Filename"],
                [[escape(filename), escape(self._sanitize(filename)) if self._check(filename) else ""] for filename in self._album_filenames(album)],
            )
            return CheckResult(
                f"illegal {pluralize('filename', issues)}: {', '.join(list(issues))}",
                Fixer(lambda _: self._fix_sanitize_filenames(album), options, False, option_automatic_index, table),
            )

    def _album_filenames(self, album: Album) -> list[str]:
        """Filenames of all album files this check inspects and sanitizes: audio tracks and picture files."""
        return [track.filename for track in album.tracks] + [picture_file.filename for picture_file in album.picture_files]

    def _check(self, filename: str) -> set[str]:
        try:
            validate_filename(filename, platform=self.ctx.config.path_compatibility)
            return set()
        except ValidationError as ex:
            return {f"{repr(ex)}"}

    def _sanitize(self, filename: str) -> str:
        return sanitize_filename(filename, replacement_text=self.ctx.config.path_replace_invalid, platform=self.ctx.config.path_compatibility)

    def _fix_sanitize_filenames(self, album: Album):
        changed = False
        for filename in self._album_filenames(album):
            new_filename = self._sanitize(filename)
            if new_filename != filename:
                self.ctx.console.print(f"Renaming {escape(filename)} to {escape(new_filename)}")
                rename(self.ctx.config.library / album.path / filename, self.ctx.config.library / album.path / new_filename)
                changed = True
        return FixResult.of(changed)
