import logging
from pathlib import Path
import re

from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album, Track
from .base_check import Check, CheckResult, Fixer, ProblemCategory


logger = logging.getLogger(__name__)

OPTION_USE_PROPOSED = ">> Use proposed track titles"


class CheckTrackTitle(Check):
    name = "track_title"
    default_config = {"enabled": True}

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None  # this check is currently not valid for files that don't have "title" tag

        no_title = sum(0 if track.tags.get("title") else 1 for track in album.tracks)
        if no_title:
            proposed_titles = list(self._proposed_title(track) for track in album.tracks)
            any_fixable = any(not track.tags.get("title") and proposed_titles[ix] for (ix, track) in enumerate(album.tracks))
            if any_fixable:
                table: tuple[list[str], list[list[str]]] = (
                    ["filename", "title", "proposed new title"],
                    [[str(track.filename), str(track.tags.get("title")), str(proposed_titles[ix])] for (ix, track) in enumerate(album.tracks)],
                )
                option_free_text = False
                option_automatic_index = None  # TODO enable
                fixer = Fixer(lambda option: self._fix(album, option), [OPTION_USE_PROPOSED], option_free_text, option_automatic_index, table)
            else:
                fixer = None
            return CheckResult(ProblemCategory.TAGS, f"{no_title} tracks missing title tag", fixer)

        return None

    def _proposed_title(self, track: Track):
        if track.tags.get("title"):
            return None
        # TODO: try to handle if spaces or special characters have been converted to underscores
        filename_parser = "(?P<track1>\\d+)?(?:-(?P<track2>\\d+)?)?(?:[\\s\\-]+|\\.\\s+)?(?P<title>.*)(?:\\s+)?\\.\\w+"
        match = re.fullmatch(filename_parser, track.filename)
        title = match.group("title") if match else None
        if title:
            return title
        return None

    def _fix(self, album: Album, option: str) -> bool:
        changed = False
        for track in album.tracks:
            file = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / track.filename
            new_title = self._proposed_title(track)
            if new_title:
                self.ctx.console.print(f"setting title on {track.filename}")
                set_basic_tags(file, [("title", new_title)])
                changed = True
        return changed
