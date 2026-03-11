import logging
import re
from typing import Sequence

from rich.markup import escape

from ...database.models import AlbumEntity, TrackEntity
from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import BasicTag
from ...types import CheckResult, Fixer
from ..base_check import Check
from .check_track_numbering import describe_track_number, ordered_tracks

logger = logging.getLogger(__name__)


OPTION_USE_PROPOSED = ">> Split track number into disc number and track number"


class CheckDiscInTrackNumber(Check):
    name = "disc-in-track-number"
    default_config = {"enabled": True}

    def check(self, album: AlbumEntity):
        if not all(AlbumTagger.supports(track.filename, Cap.FORMATTED_TRACK_NUMBER) for track in album.tracks):
            return None  # not valid if track number is not supported or is stored as an integer

        if all_tracks_discnumber_in_tracknumber(album.tracks):
            option_free_text = False
            option_automatic_index = 0
            tracks = [
                [describe_track_number(track), escape(track.filename), *self._proposed_disc_and_tracknumber(track)] for track in ordered_tracks(album)
            ]
            table = (["track", "filename", "proposed disc#", "proposed track#"], tracks)
            return CheckResult(
                "track numbers formatted as number-dash-number, probably discnumber and tracknumber",
                Fixer(lambda option: self._fix(album, option), [OPTION_USE_PROPOSED], option_free_text, option_automatic_index, table),
            )

        return None

    def _fix(self, album: AlbumEntity, option: str | None) -> bool:
        if option != OPTION_USE_PROPOSED:
            raise ValueError(f"invalid option {option}")

        for track in album.tracks:
            path = self.ctx.config.library / album.path / track.filename
            self.ctx.console.print(f"setting discnumber and tracknumber on {track.filename}")
            (discnumber, tracknumber) = self._proposed_disc_and_tracknumber(track)
            self.tagger.get(album.path).set_basic_tags(path, [(BasicTag.DISCNUMBER, discnumber), (BasicTag.TRACKNUMBER, tracknumber)])
        return True

    def _proposed_disc_and_tracknumber(self, track: TrackEntity):
        [discnumber, tracknumber] = track.get(BasicTag.TRACKNUMBER)[0].split("-")
        return (discnumber, tracknumber)


def all_tracks_discnumber_in_tracknumber(tracks: Sequence[TrackEntity]):
    any_discnumber = any(track.has(BasicTag.DISCNUMBER) for track in tracks)
    all_tracknumber_with_dashes = all(re.fullmatch("\\d+-\\d+", "|".join(track.get(BasicTag.TRACKNUMBER, default=[]))) for track in tracks)
    return not any_discnumber and all_tracknumber_with_dashes
