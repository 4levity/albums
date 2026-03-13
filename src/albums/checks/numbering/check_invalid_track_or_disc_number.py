import logging
from typing import Collection, Mapping, Sequence

from rich.markup import escape

from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import BasicTag
from ...types import Album, CheckResult, Fixer, Track
from ..base_check import Check
from .check_track_numbering import describe_track_number, ordered_tracks

logger = logging.getLogger(__name__)

OPTION_AUTOMATIC_REPAIR = ">> Automatically remove zero, non-numeric and multiple values"
SINGLE_POSITIVE_NUMBER_TAGS = [BasicTag.TRACKNUMBER, BasicTag.TRACKTOTAL, BasicTag.DISCNUMBER, BasicTag.DISCTOTAL]


class CheckInvalidTrackOrDiscNumber(Check):
    name = "invalid-track-or-disc-number"
    default_config = {"enabled": True}
    must_pass_checks = {"disc-in-track-number"}

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.FORMATTED_TRACK_NUMBER) for track in album.tracks):
            return None  # not valid if track number is not supported or is stored as an integer

        issues = get_issues_invalid_disc_or_track_number(album.tracks)

        if issues:
            option_free_text = False
            option_automatic_index = 0
            return CheckResult(
                f"bad values in track/disc number tags: {', '.join(issues)}",
                Fixer(
                    lambda option: self._fix(album, option),
                    [OPTION_AUTOMATIC_REPAIR],
                    option_free_text,
                    option_automatic_index,
                    (["track", "filename"], [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)]),
                ),
            )

        return None

    def _fix(self, album: Album, option: str) -> bool:
        if option != OPTION_AUTOMATIC_REPAIR:
            raise ValueError(f"invalid option: {option}")

        changed = False
        for track in album.tracks:
            file = self.ctx.config.library / album.path / track.filename
            new_values: list[tuple[BasicTag, str | list[str] | None]] = []
            for tag in SINGLE_POSITIVE_NUMBER_TAGS:
                track_tags = track.tag_dict()
                if tag in track_tags:
                    # gather all values for this tag that are numeric and > 0, if any
                    valid_values: set[str] = set()
                    for value in track_tags.get(tag, []):
                        if value.isdecimal() and int(value) > 0:
                            valid_values.add(value)
                    if not valid_values or len(valid_values) > 1:
                        # either there are no valid values or there's still more than one, deleting tag
                        new_value = None
                    else:
                        # there's only one value left that looks right, keep it
                        new_value = valid_values.pop()
                    if track_tags.get(tag) != (None if new_value is None else [new_value]):
                        new_values.append((tag, new_value))
            if new_values:
                self.ctx.console.print(f"setting {' and '.join(list(name for (name, _) in new_values))} on {track.filename}")
                self.tagger.get(album.path).set_basic_tags(file, new_values)
                changed = True

        return changed


def get_issues_invalid_disc_or_track_number(tracks: Sequence[Track]):
    issues: set[str] = set()
    for track in tracks:
        track_tags = track.tag_dict()
        if _has_multi_value(track_tags, SINGLE_POSITIVE_NUMBER_TAGS):
            issues.add("track/disc numbering tags with multiple values")
        if _has_non_numeric(track_tags, SINGLE_POSITIVE_NUMBER_TAGS):
            issues.add("track/disc numbering tags with non-numeric values")
        if _has_zero_value(track_tags, SINGLE_POSITIVE_NUMBER_TAGS):
            issues.add("track/disc numbering tags where the value is 0")
    return issues


def _has_multi_value(tags: Mapping[BasicTag, Sequence[str]], check_tags: Collection[BasicTag]):
    for tag in check_tags:
        if len(tags.get(tag, [])) > 1:
            return True
    return False


def _has_non_numeric(tags: Mapping[BasicTag, Sequence[str]], check_tags: Collection[BasicTag]):
    for tag_name in check_tags:
        for value in tags.get(tag_name, []):
            if not value.isdecimal():
                return True
    return False


def _has_zero_value(tags: Mapping[BasicTag, Sequence[str]], check_tags: Collection[BasicTag]):
    for tag_name in check_tags:
        for value in tags.get(tag_name, []):
            if value.isdecimal() and int(value) == 0:
                return True
    return False
