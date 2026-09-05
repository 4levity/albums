import logging
from os import rename
from typing import Final

from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.entities import Album
from albums.words import plural

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
        taken = self._existing_names(album)
        rows: list[list[str]] = []
        for track in sorted(album.tracks):
            if track.stream.error:
                new_filename = self._available_name(f"{track.filename}.unreadable", taken)
                row = [
                    escape(track.filename),
                    f"[red]{escape(track.stream.error)}[/red]",
                    f"[yellow]{escape(new_filename)}[/yellow]",
                ]
            else:
                row = [escape(track.filename), "[green]ok[/green]", "[bold italic]no change[/bold italic]"]
            rows.append(row)
        table = (["filename", "stream error", "proposed new filename"], rows)
        options = [OPTION_RENAME_UNREADABLE]
        option_automatic_index = None
        fixer = Fixer(lambda option: self._fix_rename_unreadable(album), options, False, option_automatic_index, table)
        return CheckResult(f"{plural(unreadable_count, 'unreadable track')}, example {example_filename}", fixer)

    def _fix_rename_unreadable(self, album: Album):
        changed = False
        album_path = self.ctx.config.library / album.path
        # check for collisions again in case the album folder changed since the check ran
        taken = self._existing_names(album)
        for track in sorted(album.tracks):
            if track.stream.error:
                new_filename = self._available_name(f"{track.filename}.unreadable", taken)
                taken.discard(str.lower(track.filename))
                self.ctx.console.print(f"Renaming {escape(track.filename)} to {escape(new_filename)}", highlight=False)
                rename(album_path / track.filename, album_path / new_filename)
                changed = True
        return FixResult.of(changed)

    def _existing_names(self, album: Album) -> set[str]:
        """Lowercased names of all files and folders in the album folder, used to detect collisions with proposed filenames."""
        album_path = self.ctx.config.library / album.path
        if not album_path.is_dir():
            return set()
        return {str.lower(entry.name) for entry in album_path.iterdir()}

    @staticmethod
    def _available_name(filename: str, taken: set[str]) -> str:
        """Return ``filename``, or ``filename.1``, ``filename.2`` etc. if it collides with a name in ``taken`` (case-insensitive).

        The returned name is added to ``taken`` so subsequent proposals do not collide with it either.
        """
        candidate = filename
        number = 0
        while str.lower(candidate) in taken:
            number += 1
            candidate = f"{filename}.{number}"
        taken.add(str.lower(candidate))
        return candidate
