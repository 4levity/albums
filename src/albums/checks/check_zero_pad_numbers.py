import logging
from enum import Enum, auto
from pathlib import Path
from typing import Any, List

from rich.console import RenderableType
from rich.markup import escape

from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album, Track
from .base_check import Check, CheckResult, Fixer, ProblemCategory
from .check_track_numbering import describe_track_number
from .helpers import get_tracks_by_disc

logger = logging.getLogger(__name__)


OPTION_APPLY_POLICY = ">> Apply policy"


class ZeroPadPolicy(Enum):
    IGNORE = auto()
    NEVER = auto()
    IF_NEEDED = auto()
    TWO_DIGIT_MINIMUM = auto()

    @classmethod
    def from_str(cls, selection: str):
        for policy in cls:
            if str.lower(policy.name) == str.lower(selection):
                return policy
        logger.warning(f'invalid zero pad policy "{selection}", using "ignore"')
        return cls.IGNORE


class CheckZeroPadNumbers(Check):
    name = "zero_pad_numbers"
    default_config = {
        "enabled": True,
        "tracknumber_pad": "TWO_DIGIT_MINIMUM",
        "tracktotal_pad": "two_digit_minimum",
        "discnumber_pad": "if_needed",
        "disctotal_pad": "never",
    }
    must_pass_checks = {"invalid_track_or_disc_number"}

    def init(self, check_config: dict[str, Any]):
        self.tracknumber_pad = ZeroPadPolicy.from_str(str(check_config.get("tracknumber_pad", CheckZeroPadNumbers.default_config["tracknumber_pad"])))
        self.tracktotal_pad = ZeroPadPolicy.from_str(str(check_config.get("tracktotal_pad", CheckZeroPadNumbers.default_config["tracktotal_pad"])))
        self.discnumber_pad = ZeroPadPolicy.from_str(str(check_config.get("discnumber_pad", CheckZeroPadNumbers.default_config["discnumber_pad"])))
        self.disctotal_pad = ZeroPadPolicy.from_str(str(check_config.get("disctotal_pad", CheckZeroPadNumbers.default_config["disctotal_pad"])))
        if (
            self.tracknumber_pad == ZeroPadPolicy.IGNORE
            and self.tracktotal_pad == ZeroPadPolicy.IGNORE
            and self.discnumber_pad == ZeroPadPolicy.IGNORE
            and self.disctotal_pad == ZeroPadPolicy.IGNORE
        ):
            logger.warning(f"{CheckZeroPadNumbers.name} configuration problem: all policies are set to IGNORE, nothing to do")

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None  # this check is currently not valid for files that don't use "tracknumber"/"discnumber" tags

        tracks_by_disc = get_tracks_by_disc(album.tracks)
        if tracks_by_disc is None:
            return CheckResult(ProblemCategory.TAGS, "couldn't arrange tracks by disc - invalid_track_or_disc_number check must pass first")

        total_discs = len(tracks_by_disc.keys())
        table_rows: List[List[RenderableType]] = []
        fix_tracknumbers = 0
        fix_tracktotals = 0
        fix_discnumbers = 0
        fix_disctotals = 0
        for tracks in tracks_by_disc.values():
            for track in tracks:
                table_rows.append([describe_track_number(track), escape(track.filename)])
                if (
                    "tracknumber" in track.tags
                    and self._apply_pad_policy(track.tags["tracknumber"][0], self.tracknumber_pad, len(tracks)) != track.tags["tracknumber"][0]
                ):
                    fix_tracknumbers += 1

                if (
                    "tracktotal" in track.tags
                    and self._apply_pad_policy(track.tags["tracktotal"][0], self.tracktotal_pad, len(tracks)) != track.tags["tracktotal"][0]
                ):
                    fix_tracktotals += 1

                if (
                    "discnumber" in track.tags
                    and self._apply_pad_policy(track.tags["discnumber"][0], self.discnumber_pad, total_discs) != track.tags["discnumber"][0]
                ):
                    fix_discnumbers += 1

                if (
                    "disctotal" in track.tags
                    and self._apply_pad_policy(track.tags["disctotal"][0], self.disctotal_pad, total_discs) != track.tags["disctotal"][0]
                ):
                    fix_disctotals += 1

        problems: list[str] = []
        policies: list[str] = []
        if fix_discnumbers:
            problems.append(f"{fix_discnumbers} disc numbers")
            policies.append(f"discnumber pad {self.discnumber_pad.name}")
        if fix_disctotals:
            problems.append(f"{fix_disctotals} disc totals")
            policies.append(f"disctotal pad {self.disctotal_pad.name}")
        if fix_tracknumbers:
            problems.append(f"{fix_tracknumbers} track numbers")
            policies.append(f"tracknumber pad {self.tracknumber_pad.name}")
        if fix_tracktotals:
            problems.append(f"{fix_tracktotals} track totals")
            policies.append(f"tracktotal pad {self.tracktotal_pad.name}")
        if problems:
            option_automatic_index = 0
            option_free_text = False
            return CheckResult(
                ProblemCategory.TAGS,
                f"incorrect zero padding for {' and '.join(problems)}",
                Fixer(
                    lambda option: self._fix(album, option, tracks_by_disc),
                    [f"{OPTION_APPLY_POLICY}: {' and '.join(policies)}"],
                    option_free_text,
                    option_automatic_index,
                    (["track", "filename"], table_rows),
                ),
            )

        return None

    def _apply_pad_policy(self, number_str: str, policy: ZeroPadPolicy, total_item_count: int):
        if policy == ZeroPadPolicy.NEVER:
            return str(int(number_str))

        if policy == ZeroPadPolicy.IF_NEEDED:
            if total_item_count < 10:
                return str(int(number_str))
            return f"{int(number_str):02d}" if total_item_count < 100 else f"{int(number_str):03d}"

        if policy == ZeroPadPolicy.TWO_DIGIT_MINIMUM:
            return f"{int(number_str):02d}" if total_item_count < 100 else f"{int(number_str):03d}"

        return number_str

    def _fix(self, album: Album, option: str, tracks_by_disc: dict[int, list[Track]]) -> bool:
        if not option.startswith(OPTION_APPLY_POLICY):
            raise ValueError(f"ZeroPadNumbers._fix invalid option {option}")

        changed = False
        total_discs = len(tracks_by_disc)
        for disc in tracks_by_disc.values():
            for track in disc:
                file = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / track.filename
                new_values: list[tuple[str, str | list[str] | None]] = []
                if self.tracknumber_pad != ZeroPadPolicy.IGNORE and "tracknumber" in track.tags:
                    new_tracknumber = self._apply_pad_policy(track.tags["tracknumber"][0], self.tracknumber_pad, len(disc))
                    if new_tracknumber != track.tags["tracknumber"][0]:
                        new_values.append(("tracknumber", new_tracknumber))
                if self.tracktotal_pad != ZeroPadPolicy.IGNORE and "tracktotal" in track.tags:
                    new_tracktotal = self._apply_pad_policy(track.tags["tracktotal"][0], self.tracktotal_pad, len(disc))
                    if new_tracktotal != track.tags["tracktotal"][0]:
                        new_values.append(("tracktotal", new_tracktotal))
                if self.discnumber_pad != ZeroPadPolicy.IGNORE and "discnumber" in track.tags:
                    new_discnumber = self._apply_pad_policy(track.tags["discnumber"][0], self.discnumber_pad, total_discs)
                    if new_discnumber != track.tags["discnumber"][0]:
                        new_values.append(("discnumber", new_discnumber))
                if self.disctotal_pad != ZeroPadPolicy.IGNORE and "disctotal" in track.tags:
                    new_disctotal = self._apply_pad_policy(track.tags["disctotal"][0], self.disctotal_pad, total_discs)
                    if new_disctotal != track.tags["disctotal"][0]:
                        new_values.append(("disctotal", new_disctotal))
                if new_values:
                    self.ctx.console.print(f"setting {' and '.join(list(name for (name, _) in new_values))} on {track.filename}")
                    set_basic_tags(file, new_values)
                    changed = True
        return changed
