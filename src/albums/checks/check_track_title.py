import logging
from typing import List

from rich.console import RenderableType
from rich.markup import escape

from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album, CheckResult, Fixer, ProblemCategory, Track
from .base_check import Check
from .helpers import parse_filename, show_tag

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
                table: tuple[list[str], List[List[RenderableType]]] = (
                    ["filename", "title", "proposed new title"],
                    [
                        [
                            escape(track.filename),
                            show_tag(track.tags.get("title")),
                            escape(str(proposed_titles[ix])) if proposed_titles[ix] else "[bold italic]None[/bold italic]",
                        ]
                        for (ix, track) in enumerate(album.tracks)
                    ],
                )
                option_free_text = False
                options = [OPTION_USE_PROPOSED]
                option_automatic_index = 0
                fixer = Fixer(lambda option: self._fix(album, option), options, option_free_text, option_automatic_index, table)
                return CheckResult(ProblemCategory.TAGS, f"{no_title} tracks missing title tag", fixer)

            return CheckResult(ProblemCategory.TAGS, f"{no_title} tracks missing title tag and cannot guess from filename")

        return None

    def _proposed_title(self, track: Track):
        if track.tags.get("title"):
            return None

        (_, _, title) = parse_filename(track.filename)
        # TODO: if it looks like spaces were converted to underscores, consider trying to recover
        return title

    def _fix(self, album: Album, option: str) -> bool:
        changed = False
        for track in album.tracks:
            file = self.ctx.config.library / album.path / track.filename
            new_title = self._proposed_title(track)
            if new_title:
                self.ctx.console.print(f"setting title on {track.filename}")
                set_basic_tags(file, [("title", new_title)])
                changed = True
        return changed
