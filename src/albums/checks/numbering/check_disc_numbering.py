import logging
from typing import Any, Final

from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.checks.field_policy import Policy, check_policy
from albums.checks.helpers import describe_track_number, get_tracks_by_disc, ordered_tracks, parse_filename
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField, Cap
from albums.words import plural, pluralize

logger: Final = logging.getLogger(__name__)


OPTION_REMOVE_DISC_TOTAL: Final = ">> Remove disc total field"
OPTION_SET_DISC_TOTAL: Final = ">> Set disc total"
OPTION_SET_DISCNUMBER: Final = ">> Set disc number"
OPTION_SET_DISCNUMBER_FROM_FILENAME: Final = ">> Set disc number from filename"
OPTION_REMOVE_DISCNUMBER_1: Final = ">> Remove disc number 1"

DISC_TABLE_HEADERS: Final = ["track", "filename", "discnumber", "disctotal"]


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
                    (DISC_TABLE_HEADERS, [self._disc_table_row(track) for track in ordered_tracks(album)]),
                ),
            )

        if 0 in tracks_by_disc:
            # not all tracks have a disc number
            if len(tracks_by_disc) == 1:
                return None  # no disc number or disc total on this album
            return self._check_mixed_discnumber(album, all_disc_numbers, all_disc_totals)

        # all tracks have a disc number
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

        if len(all_disc_numbers) == 1 and expect_disc_total == 1 and all_disc_numbers.pop() == 1:
            return self._check_redundant_disc_1(album, max(all_disc_totals))

        return None

    def _check_mixed_discnumber(self, album: Album, all_disc_numbers: set[int], all_disc_totals: list[int]) -> CheckResult:
        # here, disc total is either on no tracks or on all tracks (with a single value) or the check would have reported an inconsistent total already
        unnumbered = [track for track in album.tracks if not track.has(BasicField.DISCNUMBER)]
        disctotal = max(all_disc_totals)  # 0 if no disc total
        discs_present = all_disc_numbers - {0}

        # if we can read a disc number from every unnumbered track's filename, and no filename disagrees with an existing disc number,
        # the filenames can be offered as the fix
        filename_discs: dict[str, int | None] = {}
        filename_conflict = False
        for track in album.tracks:
            (disc, _, _) = parse_filename(track.filename)
            if track.has(BasicField.DISCNUMBER):
                if disc is not None and disc != int(track.get(BasicField.DISCNUMBER)[0]):
                    filename_conflict = True
            else:
                filename_discs[track.filename] = disc
        filename_ok = all(filename_discs.values()) and not filename_conflict
        # can we set disc number 1 on the unnumbered tracks? only if no disc number other than 1 is in play
        consistent_with_1 = all(disc in (None, 1) for disc in filename_discs.values())
        only_disc_1 = discs_present == {1} and disctotal <= 1

        options: list[str] = []
        option_automatic_index: int | None = None
        option_a = f"{OPTION_SET_DISCNUMBER_FROM_FILENAME} on {plural(len(unnumbered), 'track')}"
        option_b = f"{OPTION_SET_DISCNUMBER} = 1 on {plural(len(unnumbered), 'track')}"
        if filename_ok:
            # every unnumbered track's filename gives a disc number and no filename disagrees with an existing disc number
            proposed = discs_present | {disc for disc in filename_discs.values() if disc is not None}
            # automatically fixable if the resulting disc numbers are sequential from 1 and don't exceed the disc total
            auto_from_filename = proposed == set(range(1, max(proposed) + 1)) and (disctotal == 0 or disctotal >= max(proposed))
            if any(disc > 1 for disc in filename_discs.values() if disc is not None):
                options.append(option_a)
                option_automatic_index = 0 if auto_from_filename else None
            elif only_disc_1:
                # single-disc album, so set the unnumbered tracks to disc 1 (matching the filenames) or remove
                if self.remove_redundant_discnumber:
                    options.append(self._remove_disc_1_option(disctotal))
                    options.append(option_b)
                else:
                    options.append(option_b)
                    options.append(self._remove_disc_1_option(disctotal))
                option_automatic_index = 0
            else:
                options.append(option_a)
                option_automatic_index = 0 if auto_from_filename else None
        elif only_disc_1 and consistent_with_1:
            # the only disc number seen is 1, with no contradictory filename
            if self.remove_redundant_discnumber:
                options.append(self._remove_disc_1_option(disctotal))
                options.append(option_b)
            else:
                options.append(option_b)
                options.append(self._remove_disc_1_option(disctotal))
            option_automatic_index = 0
        # otherwise there is no obvious fix, but the user can enter a disc number to set on the unnumbered tracks

        message = f"some tracks have disc number and some do not ({plural(len(unnumbered), 'track')} without disc number)"
        return CheckResult(
            message,
            Fixer(
                lambda option: self._fix_discnumber_mixed(album, option),
                options,
                True,
                option_automatic_index,
                (DISC_TABLE_HEADERS, [self._disc_table_row(track) for track in ordered_tracks(album)]),
            ),
        )

    def _check_redundant_disc_1(self, album: Album, disc_total: int) -> CheckResult | None:
        # every track has disc number 1, and disc total 1 if present
        if self.remove_redundant_discnumber:
            option_automatic_index = 0
        elif self.discs_in_separate_folders:
            return None  # disc 1 might be part of a multi-disc set stored in separate folders
        else:
            option_automatic_index = None  # offer to remove, but not automatically
        disctotal_notice = " and disc total 1" if disc_total else ""
        options = [f"{OPTION_REMOVE_DISCNUMBER_1}{disctotal_notice} from all tracks"]
        return CheckResult(
            f"Apparently redundant disc number 1{disctotal_notice}",
            Fixer(
                lambda _: self._fix_remove_disc_number_disc_total_1(album),
                options,
                False,
                option_automatic_index,
                (DISC_TABLE_HEADERS, [self._disc_table_row(track) for track in ordered_tracks(album)]),
            ),
        )

    @staticmethod
    def _remove_disc_1_option(disctotal: int) -> str:
        return f"{OPTION_REMOVE_DISCNUMBER_1}{' and disc total 1' if disctotal else ''} from all tracks"

    @staticmethod
    def _disc_table_row(track: Track) -> list[str]:
        return [
            describe_track_number(track),
            escape(track.filename),
            track.get(BasicField.DISCNUMBER, default=[""])[0],
            track.get(BasicField.DISCTOTAL, default=[""])[0],
        ]

    def _fix_disc_total(self, album: Album, option: str):
        if option.startswith(OPTION_SET_DISC_TOTAL):
            value = option.split(" = ")[1]
        elif option.startswith(OPTION_REMOVE_DISC_TOTAL):
            value = None
        elif option.isdecimal():  # free text
            if int(option) < 1:
                logger.error(f"invalid disc total: {option}")
                return FixResult.NO_CHANGE
            value = option
        else:
            logger.error(f"invalid option for disc total fix: {option}")
            return FixResult.NO_CHANGE

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

    def _fix_discnumber_mixed(self, album: Album, option: str) -> FixResult:
        if option.startswith(OPTION_SET_DISCNUMBER_FROM_FILENAME):
            return self._fix_set_discnumber_from_filename(album)
        if option.startswith(OPTION_REMOVE_DISCNUMBER_1):
            return self._fix_remove_disc_number_disc_total_1(album)
        if option.startswith(OPTION_SET_DISCNUMBER):
            value_str = option.split(" = ", 1)[1].split(" ", 1)[0]
        elif option.isdecimal():  # free text
            value_str = option
        else:
            logger.error(f"invalid option for disc number fix: {option}")
            return FixResult.NO_CHANGE
        value = int(value_str)
        if value < 1:
            logger.error(f"invalid disc number: {value}")
            return FixResult.NO_CHANGE
        return self._fix_set_discnumber(album, value)

    def _fix_set_discnumber(self, album: Album, value: int) -> FixResult:
        changed = False
        for track in sorted(album.tracks):
            if track.has(BasicField.DISCNUMBER):
                continue
            path = self.ctx.config.library / album.path / track.filename
            self.ctx.console.print(f"setting discnumber {value} on {escape(track.filename)}", highlight=False)
            self.tagger.get(album.path).set_basic_fields(path, [(BasicField.DISCNUMBER, str(value))])
            changed = True
        return FixResult.of(changed)

    def _fix_set_discnumber_from_filename(self, album: Album) -> FixResult:
        changed = False
        for track in sorted(album.tracks):
            if track.has(BasicField.DISCNUMBER):
                continue
            (disc, _, _) = parse_filename(track.filename)
            if disc is None:
                raise ValueError(f"cannot set disc number from filename for {track.filename}")
            path = self.ctx.config.library / album.path / track.filename
            self.ctx.console.print(f"setting discnumber {disc} from filename on {escape(track.filename)}", highlight=False)
            self.tagger.get(album.path).set_basic_fields(path, [(BasicField.DISCNUMBER, str(disc))])
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
