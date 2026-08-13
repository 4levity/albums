import logging
from typing import Any, Final

from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.checks.field_policy import Policy, check_policy
from albums.checks.helpers import describe_track_number, get_tracks_by_disc, ordered_tracks
from albums.entities import Album
from albums.tagger.folder import AlbumTagger, Cap
from albums.tagger.types import BasicField
from albums.words import pluralize

logger: Final = logging.getLogger(__name__)


OPTION_REMOVE_DISC_TOTAL: Final = ">> Remove disc total field"
OPTION_SET_DISC_TOTAL: Final = ">> Set disc total"


class CheckDiscNumbering(Check):
    name = "disc-numbering"
    default_config = {"enabled": True, "discs_in_separate_folders": True, "disctotal_policy": "consistent", "remove_redundant_discnumber": False}
    must_pass_checks = {"legacy-fields", "invalid-track-or-disc-number"}

    def init(self, check_config: dict[str, Any]):
        self.discs_in_separate_folders = check_config.get("discs_in_separate_folders", self.default_config["discs_in_separate_folders"])
        self.disctotal_policy = Policy.from_str(str(check_config.get("disctotal_policy", self.default_config["disctotal_policy"])))
        self.remove_redundant_discnumber = bool(check_config.get("remove_redundant_discnumber", self.default_config["remove_redundant_discnumber"]))
        if self.remove_redundant_discnumber and self.discs_in_separate_folders:
            raise ValueError("disc-numbering check cannot have discs_in_separate_folders=True and remove_redundant_discnumber=True at the same time")

    def check(self, album: Album) -> CheckResult | None:
        if not all(AlbumTagger.supports(track.filename, Cap.FORMATTED_TRACK_NUMBER) for track in album.tracks):
            return None  # not valid if track number is not supported or is stored as an integer

        tracks_by_disc = get_tracks_by_disc(album.tracks)
        if not tracks_by_disc:
            return CheckResult("couldn't arrange tracks by disc - invalid-track-or-disc-number check must pass first")
        # now, all tracknumber/tracktotal/discnumber/disctotal fields should be single-valued and numeric

        single_value_for_album = self.disctotal_policy != Policy.NEVER
        disctotal_result = check_policy(
            self.ctx, self.tagger.get(album.path), album, self.disctotal_policy, BasicField.DISCTOTAL, BasicField.DISCNUMBER, single_value_for_album
        )
        if disctotal_result:
            # TODO if policy is "always" and some fields are missing, we could ignore it and automatically fix them instead
            return disctotal_result

        # we look at total before looking at the disc number values in order to extract the most value out of the totals -- a correct total helps
        # confirm disc numbering is correct, so totals that "look wrong" should ideally be fixed (or automatically removed) first.
        all_disc_numbers = set(int(track.get(BasicField.DISCNUMBER, default=["0"])[0]) for track in album.tracks)
        all_disc_totals = list(set(int(track.get(BasicField.DISCTOTAL, default=["0"])[0]) for track in album.tracks))
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
                message,
                Fixer(
                    lambda option: self._fix_disc_total(album, option),
                    options,
                    option_free_text,
                    option_automatic_index,
                    (["track", "filename"], [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)]),
                ),
            )

        # TODO offer fixer if disc numbers in filenames look right
        if 0 in tracks_by_disc:
            # not all tracks have a disc number
            if len(tracks_by_disc) == 1:
                return None  # no disc number or disc total on this album
            else:
                return CheckResult("some tracks have disc number and some do not")
        else:  # all tracks have a disc number
            # TODO if discs_in_separate_folders=False and disc is 1 or 1/1 then offer to remove discnumber/disctotal (not automatic)

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
                        f"album only has a single disc {list(all_disc_numbers)[0]} of {expect_disc_total} (if this is wanted, enable discs_in_separate_folders)",
                    )
            elif missing_disc_numbers:
                return CheckResult(f"missing disc {pluralize('number', missing_disc_numbers)}: {missing_disc_numbers}")

            unexpected_disc_numbers = all_disc_numbers - expect_disc_numbers
            if unexpected_disc_numbers:
                return CheckResult(f"unexpected disc {pluralize('number', unexpected_disc_numbers)}: {unexpected_disc_numbers}")

            if self.remove_redundant_discnumber and len(all_disc_numbers) == 1 and expect_disc_total == 1 and all_disc_numbers.pop() == 1:
                disctotal_notice = " and disc total 1" if max(all_disc_totals) else ""
                options = [f">> Remove disc number 1{disctotal_notice} from all tracks"]
                option_automatic_index = 0
                return CheckResult(
                    f"Apparently redundant disc number 1{disctotal_notice}",
                    Fixer(
                        lambda _: self._fix_remove_disc_number_disc_total_1(album),
                        options,
                        False,
                        option_automatic_index,
                        (["track", "filename"], [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)]),
                    ),
                )

        return None

    def _fix_disc_total(self, album: Album, option: str):
        if option.startswith(OPTION_SET_DISC_TOTAL):
            value = option.split(" = ")[1]
        elif option.startswith(OPTION_REMOVE_DISC_TOTAL):
            value = None
        else:
            raise ValueError(f"invalid option {option}")

        changed = False
        for track in sorted(album.tracks):
            path = self.ctx.config.library / album.path / track.filename
            if value is None and track.has(BasicField.DISCTOTAL):
                self.ctx.console.print(f"removing disctotal from {escape(track.filename)}", highlight=False)
                self.tagger.get(album.path).set_basic_fields(path, [(BasicField.DISCTOTAL, None)])
                changed = True
            if value is not None and (not track.has(BasicField.DISCTOTAL) or int(track.get(BasicField.DISCTOTAL)[0]) != int(value)):
                self.ctx.console.print(f"setting disctotal on {escape(track.filename)}", highlight=False)
                self.tagger.get(album.path).set_basic_fields(path, [(BasicField.DISCTOTAL, value)])
                changed = True
        return FixResult.of(changed)

    def _fix_remove_disc_number_disc_total_1(self, album: Album):
        changed = False
        tagger = self.tagger.get(album.path)
        for track in (track for track in album.tracks if (track.has(BasicField.DISCNUMBER) or track.has(BasicField.DISCTOTAL))):
            remove_fields: list[BasicField] = []
            if track.has(BasicField.DISCNUMBER):
                if int(track.get(BasicField.DISCNUMBER)[0]) != 1:
                    raise ValueError(f"asked to remove disc number but it was not 1: {track.get(BasicField.DISCNUMBER)}")
                remove_fields.append(BasicField.DISCNUMBER)
            if track.has(BasicField.DISCTOTAL):
                if int(track.get(BasicField.DISCTOTAL)[0]) != 1:
                    raise ValueError(f"asked to remove disc total but it was not 1: {track.get(BasicField.DISCTOTAL)}")
                remove_fields.append(BasicField.DISCTOTAL)
            self.ctx.console.print(f"removing {' and '.join(remove_field.value for remove_field in remove_fields)} from {escape(track.filename)}")
            with tagger.open(track.filename) as tag:
                for remove_field in remove_fields:
                    tag.set_field(remove_field, None)
            changed = True
        return FixResult.of(changed)
