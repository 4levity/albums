import logging
from os import rename

from pathvalidate import ValidationError, sanitize_filename, validate_filename
from rich.markup import escape

from ...types import Album, CheckResult, Fixer
from ..base_check import Check

logger = logging.getLogger(__name__)


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
                [[escape(track.filename), escape(self._sanitize(track.filename)) if self._check(track.filename) else ""] for track in album.tracks],
            )
            return CheckResult(
                f"illegal filenames: {', '.join(list(issues))}",
                Fixer(lambda _: self._fix_sanitize_filenames(album), options, False, option_automatic_index, table),
            )

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
        for track in album.tracks:
            new_filename = self._sanitize(track.filename)
            if new_filename != track.filename:
                self.ctx.console.print(f"Renaming {escape(track.filename)} to {escape(new_filename)}")
                rename(self.ctx.config.library / album.path / track.filename, self.ctx.config.library / album.path / new_filename)
                changed = True
        return changed
