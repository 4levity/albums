import logging
from typing import Any


from ..library.metadata import album_is_basic_taggable
from ..types import Album
from .base_check import Check, CheckResult, ProblemCategory
from .helpers import get_tracks_by_disc


logger = logging.getLogger(__name__)


class CheckDiscNumbering(Check):
    name = "disc_numbering"
    default_config = {"enabled": "true", "discs_in_separate_folders": True}

    def init(self, check_config: dict[str, Any]):
        self.discs_in_separate_folders = check_config.get("discs_in_separate_folders", CheckDiscNumbering.default_config["discs_in_separate_folders"])

    def check(self, album: Album) -> CheckResult | None:
        if not album_is_basic_taggable(album):
            return None  # this check works for tracks with "tracknumber" tag

        tracks_by_disc = get_tracks_by_disc(album.tracks)
        if not tracks_by_disc:
            return CheckResult(
                ProblemCategory.TAGS, "couldn't arrange tracks by disc - disc_in_track_number and invalid_track_or_disc_number checks must pass first"
            )

        # now, all tracknumber/tracktotal/discnumber/disctotal tags are guaranteed single-valued and numeric

        # ensure no issues with disc number
        if 0 in tracks_by_disc:
            # not all tracks have a disc number
            if len(tracks_by_disc) > 1:
                return CheckResult(ProblemCategory.TAGS, "some tracks have disc number and some do not")
        else:
            # all tracks have a disc number
            all_disc_numbers = set((int(track.tags["discnumber"][0]) if "discnumber" in track.tags else 0) for track in album.tracks)
            expect_disc_total = max(len(all_disc_numbers), *all_disc_numbers)

            if expect_disc_total > 1 and len(all_disc_numbers) == 1 and not self.discs_in_separate_folders:
                # expecting more than one disc in this set, but this folder (album) only has one disc
                return CheckResult(
                    ProblemCategory.TAGS,
                    f"album only has disc {list(all_disc_numbers)[0]} of {expect_disc_total} disc album (if this is wanted, enable discs_in_separate_folders)",
                )

            expect_disc_numbers = set(range(1, expect_disc_total + 1))
            missing_disc_numbers = expect_disc_numbers - all_disc_numbers
            if missing_disc_numbers:
                return CheckResult(ProblemCategory.TAGS, f"missing disc numbers: {missing_disc_numbers}")

            unexpected_disc_numbers = all_disc_numbers - expect_disc_numbers
            if unexpected_disc_numbers:
                return CheckResult(ProblemCategory.TAGS, f"unexpected disc numbers: {unexpected_disc_numbers}")
