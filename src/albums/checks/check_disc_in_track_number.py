import logging
import re
from pathlib import Path

from rich.markup import escape

from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album, Track
from .base_check import Check, CheckResult, Fixer, ProblemCategory
from .check_track_numbering import describe_track_number, ordered_tracks

logger = logging.getLogger(__name__)


OPTION_USE_PROPOSED = ">> Split track number into disc number and track number"


class CheckDiscInTrackNumber(Check):
    name = "disc_in_track_number"
    default_config = {"enabled": True}

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None  # this check is not valid for files where albums doesn't know about the noted tags

        if all_tracks_discnumber_in_tracknumber(album.tracks):
            option_free_text = False
            option_automatic_index = 0
            tracks = [
                [describe_track_number(track), escape(track.filename), *self._proposed_disc_and_tracknumber(track)] for track in ordered_tracks(album)
            ]
            table = (["track", "filename", "proposed disc#", "proposed track#"], tracks)
            return CheckResult(
                ProblemCategory.TAGS,
                "track numbers formatted as number-dash-number, probably discnumber and tracknumber",
                Fixer(lambda option: self._fix(album, option), [OPTION_USE_PROPOSED], option_free_text, option_automatic_index, table),
            )

        return None

    def _fix(self, album: Album, option: str | None) -> bool:
        if option != OPTION_USE_PROPOSED:
            raise ValueError(f"invalid option {option}")

        for track in album.tracks:
            path = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / track.filename
            self.ctx.console.print(f"setting discnumber and tracknumber on {track.filename}")
            (discnumber, tracknumber) = self._proposed_disc_and_tracknumber(track)
            set_basic_tags(path, [("discnumber", discnumber), ("tracknumber", tracknumber)])
        return True

    def _proposed_disc_and_tracknumber(self, track: Track):
        [discnumber, tracknumber] = track.tags["tracknumber"][0].split("-")
        return (discnumber, tracknumber)


def all_tracks_discnumber_in_tracknumber(tracks: list[Track]):
    any_discnumber = any("discnumber" in track.tags for track in tracks)
    all_tracknumber_with_dashes = all(re.fullmatch("\\d+-\\d+", "|".join(track.tags.get("tracknumber", []))) for track in tracks)
    return not any_discnumber and all_tracknumber_with_dashes
