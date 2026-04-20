import logging
from os import rename
from typing import Final

from rich.markup import escape

from ...types import Album, CheckResult, Fixer, FixResult
from ...words.make import plural
from ..base_check import Check

logger: Final = logging.getLogger(__name__)


OPTION_RENAME_UNREADABLE: Final = ">> Rename unreadable tracks to <filename>.unreadable"


class CheckUnreadableTrack(Check):
    name = "unreadable-track"
    default_config = {"enabled": True}

    def check(self, album: Album):
        unreadable_count = sum(1 if track.stream.error else 0 for track in album.tracks)
        if unreadable_count == 0:
            return None
        example_filename = next(track.filename for track in album.tracks if track.stream.error)
        table = (["filename", "stream error"], [[escape(track.filename), escape(track.stream.error)] for track in sorted(album.tracks)])
        options = [OPTION_RENAME_UNREADABLE]
        option_automatic_index = None
        fixer = Fixer(lambda option: self._fix_rename_unreadable(album), options, False, option_automatic_index, table)
        return CheckResult(f"{plural(unreadable_count, 'unreadable track')}, example {example_filename}", fixer)

    def _fix_rename_unreadable(self, album: Album):
        changed = False
        for track in sorted(album.tracks):
            if track.stream.error:
                new_filename = f"{track.filename}.unreadable"
                self.ctx.console.print(f"Renaming {escape(track.filename)} to {escape(new_filename)}", highlight=False)
                rename(self.ctx.config.library / album.path / track.filename, self.ctx.config.library / album.path / new_filename)
                changed = True
        return FixResult.of(changed)
