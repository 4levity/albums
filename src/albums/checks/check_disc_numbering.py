import logging
from pathlib import Path
from typing import Any

from rich.markup import escape

from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album
from . import total_tags
from .base_check import Check, CheckResult, Fixer, ProblemCategory
from .helpers import describe_track_number, get_tracks_by_disc, ordered_tracks

logger = logging.getLogger(__name__)


OPTION_REMOVE_DISC_TOTAL = ">> Remove disc total tag"
OPTION_SET_DISC_TOTAL = ">> Set disc total"


class CheckDiscNumbering(Check):
    name = "disc_numbering"
    default_config = {"enabled": "true", "discs_in_separate_folders": True, "disctotal_policy": "consistent"}
    must_pass_checks = {"invalid_track_or_disc_number"}

    def init(self, check_config: dict[str, Any]):
        self.discs_in_separate_folders = check_config.get("discs_in_separate_folders", self.default_config["discs_in_separate_folders"])
        self.disctotal_policy = total_tags.Policy.from_str(str(check_config.get("disctotal_policy", self.default_config["disctotal_policy"])))

    def check(self, album: Album) -> CheckResult | None:
        if not album_is_basic_taggable(album):
            return None  # this check works for tracks with "tracknumber" tag

        tracks_by_disc = get_tracks_by_disc(album.tracks)
        if not tracks_by_disc:
            return CheckResult(ProblemCategory.TAGS, "couldn't arrange tracks by disc - invalid_track_or_disc_number check must pass first")
        # now, all tracknumber/tracktotal/discnumber/disctotal tags should be single-valued and numeric

        # apply disc total policy - will offer automatic fix (remove all disc totals) if policy is not "always"
        option_free_text = True  # fix will allow manual entry - this is ignored if policy = "never"
        disctotal_result = total_tags.check_policy(self.ctx, album, self.disctotal_policy, "disctotal", "discnumber", option_free_text)
        if disctotal_result:
            # TODO if policy is "always" and some tags are missing, we could ignore it and automatically fix them instead
            return disctotal_result

        # we look at total before looking at the disc number values in order to extract the most value out of the totals -- a correct total helps
        # confirm disc numbering is correct, so totals that "look wrong" should ideally be fixed (or automatically removed) first.
        all_disc_numbers = set(int(track.tags.get("discnumber", [0])[0]) for track in album.tracks)
        all_disc_totals = list(set(int(track.tags.get("disctotal", [0])[0]) for track in album.tracks))
        if len(all_disc_totals) > 1:
            message = "inconsistent disc total"
        else:
            message = None  # if the disc total is consistent, trust it - conflicting disc numbers will be treated as missing/unexpected

        if message:
            options = [f"{OPTION_SET_DISC_TOTAL} = {len(all_disc_numbers)}"]
            if max(all_disc_numbers) != len(all_disc_numbers):
                options.append(f"{OPTION_SET_DISC_TOTAL} = {max(all_disc_numbers)}")
            options.append(OPTION_REMOVE_DISC_TOTAL)
            if len(all_disc_numbers) == max(all_disc_numbers) and 0 not in all_disc_numbers:
                option_automatic_index = 0
            else:
                option_automatic_index = None
            option_free_text = True
            return CheckResult(
                ProblemCategory.TAGS,
                message,
                Fixer(
                    lambda option: self._fix_disc_total(album, option),
                    options,
                    option_free_text,
                    option_automatic_index,
                    (["track", "filename"], [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)]),
                ),
            )

        if 0 in tracks_by_disc:
            # not all tracks have a disc number
            if len(tracks_by_disc) == 1:
                return None  # no disc number or disc total on this album
            else:
                # TODO offer fixer if disc numbers in filenames look right
                return CheckResult(ProblemCategory.TAGS, "some tracks have disc number and some do not")
        else:  # all tracks have a disc number
            # discs should be numbered 1..disc total, but if there is no disc total, use 1..(# of discs) or 1..(highest disc number), whichever is more
            expect_disc_total = max(all_disc_totals)
            if expect_disc_total == 0:
                expect_disc_total = max(len(all_disc_numbers), *all_disc_numbers)

            expect_disc_numbers = set(range(1, expect_disc_total + 1))
            missing_disc_numbers = expect_disc_numbers - all_disc_numbers

            if expect_disc_total > 1 and len(all_disc_numbers) == 1:
                # special case for exactly one disc in a folder but disc total indicates there are more
                if not self.discs_in_separate_folders:
                    return CheckResult(
                        ProblemCategory.TAGS,
                        f"album only has a single disc {list(all_disc_numbers)[0]} of {expect_disc_total} (if this is wanted, enable discs_in_separate_folders)",
                    )
            elif missing_disc_numbers:
                # TODO offer fixer if disc numbers in filenames look right
                return CheckResult(ProblemCategory.TAGS, f"missing disc numbers: {missing_disc_numbers}")

            unexpected_disc_numbers = all_disc_numbers - expect_disc_numbers
            if unexpected_disc_numbers:
                # TODO offer fixer if disc numbers in filenames look right
                return CheckResult(ProblemCategory.TAGS, f"unexpected disc numbers: {unexpected_disc_numbers}")

        return None

    def _fix_disc_total(self, album: Album, option: str) -> bool:
        if option.startswith(OPTION_SET_DISC_TOTAL):
            value = option.split(" = ")[1]
        elif option.startswith(OPTION_REMOVE_DISC_TOTAL):
            value = None
        else:
            raise ValueError(f"invalid option {option}")

        changed = False
        for track in album.tracks:
            path = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / track.filename
            if value is None and "disctotal" in track.tags:
                self.ctx.console.print(f"removing disctotal from {track.filename}")
                changed |= set_basic_tags(path, [("disctotal", None)])
            if value is not None and ("disctotal" not in track.tags or int(track.tags["disctotal"][0]) != int(value)):
                self.ctx.console.print(f"setting disctotal on {track.filename}")
                changed |= set_basic_tags(path, [("disctotal", value)])
        return changed
