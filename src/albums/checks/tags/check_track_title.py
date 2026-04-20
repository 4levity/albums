import logging
from typing import Final

from rich.markup import escape

from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import BasicTag
from ...types import Album, CheckResult, Fixer, FixResult, Track
from ...words.make import plural
from ..base_check import Check
from ..helpers import parse_filename, show_tag

logger: Final = logging.getLogger(__name__)

OPTION_USE_PROPOSED: Final = ">> Use proposed track titles"


class CheckTrackTitle(Check):
    name = "track-title"
    default_config = {"enabled": True}

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_TAGS) for track in album.tracks):
            return None

        no_title = sum(0 if track.get(BasicTag.TITLE, default="") else 1 for track in album.tracks)
        if no_title:
            proposed_titles = list(self._proposed_title(track) for track in sorted(album.tracks))
            any_fixable = any(not track.get(BasicTag.TITLE, default="") and proposed_titles[ix] for (ix, track) in enumerate(album.tracks))
            if any_fixable:
                table = (
                    ["filename", "title", "proposed new title"],
                    [
                        [
                            escape(track.filename),
                            show_tag(track.get(BasicTag.TITLE, default=None)),
                            escape(str(proposed_titles[ix])) if proposed_titles[ix] else "[bold italic]None[/bold italic]",
                        ]
                        for (ix, track) in enumerate(sorted(album.tracks))
                    ],
                )
                option_free_text = False
                options = [OPTION_USE_PROPOSED]
                option_automatic_index = 0
                fixer = Fixer(lambda _: self._fix(album), options, option_free_text, option_automatic_index, table)
                return CheckResult(f"{plural(no_title, 'track')} missing title tag", fixer)

            return CheckResult(f"{plural(no_title, 'track')} missing title tag and cannot guess from filename")

        return None

    def _proposed_title(self, track: Track):
        if track.get(BasicTag.TITLE, default=""):
            return None

        (_, _, title) = parse_filename(track.filename)
        # TODO: if it looks like spaces were converted to underscores, consider trying to recover
        return title

    def _fix(self, album: Album):
        changed = False
        for track in sorted(album.tracks):
            file = self.ctx.config.library / album.path / track.filename
            new_title = self._proposed_title(track)
            if new_title:
                self.ctx.console.print(f"setting title on {escape(track.filename)}", highlight=False)
                self.tagger.get(album.path).set_basic_tags(file, [(BasicTag.TITLE, new_title)])
                changed = True
        return FixResult.of(changed)
