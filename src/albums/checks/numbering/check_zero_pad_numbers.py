import logging
from enum import Enum, auto
from typing import Any, Mapping, Sequence

from rich.console import RenderableType
from rich.markup import escape

from ...database.models import AlbumEntity, TrackEntity
from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import BasicTag
from ...types import CheckResult, Fixer
from ..base_check import Check
from ..helpers import get_tracks_by_disc
from .check_track_numbering import describe_track_number

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


def apply_pad_policy(number_str: str, policy: ZeroPadPolicy, total_item_count: int) -> str:
    if policy == ZeroPadPolicy.NEVER:
        return str(int(number_str))

    if policy == ZeroPadPolicy.IF_NEEDED:
        if total_item_count < 10:
            return str(int(number_str))
        return f"{int(number_str):02d}" if total_item_count < 100 else f"{int(number_str):03d}"

    if policy == ZeroPadPolicy.TWO_DIGIT_MINIMUM:
        return f"{int(number_str):02d}" if total_item_count < 100 else f"{int(number_str):03d}"

    return number_str


class CheckZeroPadNumbers(Check):
    name = "zero-pad-numbers"
    default_config = {
        "enabled": True,
        "tracknumber_pad": "two_digit_minimum",
        "tracktotal_pad": "two_digit_minimum",
        "discnumber_pad": "if_needed",
        "disctotal_pad": "never",
    }
    must_pass_checks = {"invalid-track-or-disc-number"}

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

    def check(self, album: AlbumEntity):
        if not all(AlbumTagger.supports(track.filename, Cap.FORMATTED_TRACK_NUMBER) for track in album.tracks):
            return None  # not valid if track number is not supported or is stored as an integer

        tracks_by_disc = get_tracks_by_disc(album.tracks)
        if tracks_by_disc is None:
            return CheckResult("couldn't arrange tracks by disc - invalid-track-or-disc-number check must pass first")

        total_discs = len(tracks_by_disc.keys())
        table_rows: Sequence[Sequence[RenderableType]] = []
        fix_tracknumbers = 0
        fix_tracktotals = 0
        fix_discnumbers = 0
        fix_disctotals = 0
        for tracks in tracks_by_disc.values():
            for track in tracks:
                table_rows.append([describe_track_number(track), escape(track.filename)])
                if (
                    track.has(BasicTag.TRACKNUMBER)
                    and apply_pad_policy(track.get(BasicTag.TRACKNUMBER)[0], self.tracknumber_pad, len(tracks)) != track.get(BasicTag.TRACKNUMBER)[0]
                ):
                    fix_tracknumbers += 1

                if (
                    track.has(BasicTag.TRACKTOTAL)
                    and apply_pad_policy(track.get(BasicTag.TRACKTOTAL)[0], self.tracktotal_pad, len(tracks)) != track.get(BasicTag.TRACKTOTAL)[0]
                ):
                    fix_tracktotals += 1

                if (
                    track.has(BasicTag.DISCNUMBER)
                    and apply_pad_policy(track.get(BasicTag.DISCNUMBER)[0], self.discnumber_pad, total_discs) != track.get(BasicTag.DISCNUMBER)[0]
                ):
                    fix_discnumbers += 1

                if (
                    track.has(BasicTag.DISCTOTAL)
                    and apply_pad_policy(track.get(BasicTag.DISCTOTAL)[0], self.disctotal_pad, total_discs) != track.get(BasicTag.DISCTOTAL)[0]
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

    def _fix(self, album: AlbumEntity, option: str, tracks_by_disc: Mapping[int, Sequence[TrackEntity]]) -> bool:
        if not option.startswith(OPTION_APPLY_POLICY):
            raise ValueError(f"ZeroPadNumbers._fix invalid option {option}")

        changed = False
        total_discs = len(tracks_by_disc)
        for disc in tracks_by_disc.values():
            for track in disc:
                file = self.ctx.config.library / album.path / track.filename
                new_values: list[tuple[BasicTag, str | list[str] | None]] = []

                if self.tracknumber_pad != ZeroPadPolicy.IGNORE and track.has(BasicTag.TRACKNUMBER):
                    new_tracknumber = apply_pad_policy(track.get(BasicTag.TRACKNUMBER)[0], self.tracknumber_pad, len(disc))
                    if new_tracknumber != track.get(BasicTag.TRACKNUMBER)[0]:
                        new_values.append((BasicTag.TRACKNUMBER, new_tracknumber))

                if self.tracktotal_pad != ZeroPadPolicy.IGNORE and track.has(BasicTag.TRACKTOTAL):
                    new_tracktotal = apply_pad_policy(track.get(BasicTag.TRACKTOTAL)[0], self.tracktotal_pad, len(disc))
                    if new_tracktotal != track.get(BasicTag.TRACKTOTAL)[0]:
                        new_values.append((BasicTag.TRACKTOTAL, new_tracktotal))

                if self.discnumber_pad != ZeroPadPolicy.IGNORE and track.has(BasicTag.DISCNUMBER):
                    new_discnumber = apply_pad_policy(track.get(BasicTag.DISCNUMBER)[0], self.discnumber_pad, total_discs)
                    if new_discnumber != track.get(BasicTag.DISCNUMBER)[0]:
                        new_values.append((BasicTag.DISCNUMBER, new_discnumber))

                if self.disctotal_pad != ZeroPadPolicy.IGNORE and track.has(BasicTag.DISCTOTAL):
                    new_disctotal = apply_pad_policy(track.get(BasicTag.DISCTOTAL)[0], self.disctotal_pad, total_discs)
                    if new_disctotal != track.get(BasicTag.DISCTOTAL)[0]:
                        new_values.append((BasicTag.DISCTOTAL, new_disctotal))

                if new_values:
                    self.ctx.console.print(f"setting {' and '.join(list(name for (name, _) in new_values))} on {track.filename}")
                    self.tagger.get(album.path).set_basic_tags(file, new_values)
                    changed = True
        return changed
