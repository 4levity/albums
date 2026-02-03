import logging
from pathlib import Path

from albums.checks.check_track_number import describe_track_number, ordered_tracks

from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album, Track
from .base_check import Check, CheckResult, Fixer, ProblemCategory


logger = logging.getLogger(__name__)

OPTION_AUTOMATIC_REPAIR = ">> Automatically remove zero, non-numeric and multiple values"
SINGLE_POSITIVE_NUMBER_TAGS = ["tracknumber", "tracktotal", "discnumber", "disctotal"]


class CheckInvalidTrackOrDiscNumber(Check):
    name = "invalid_track_or_disc_number"
    default_config = {"enabled": True}
    must_pass_checks = {"disc_in_track_number"}

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None  # this check is not valid for files where albums doesn't know about the noted tags

        issues = get_issues_invalid_disc_or_track_number(album.tracks)

        if issues:
            option_free_text = False
            option_automatic_index = 0
            return CheckResult(
                ProblemCategory.TAGS,
                f"bad values in track/disc number tags: {', '.join(issues)}",
                Fixer(
                    lambda option: self._fix(album, option),
                    [OPTION_AUTOMATIC_REPAIR],
                    option_free_text,
                    option_automatic_index,
                    (["track", "filename"], [[describe_track_number(track), track.filename] for track in ordered_tracks(album)]),
                ),
            )

        return None

    def _fix(self, album: Album, option: str) -> bool:
        if option != OPTION_AUTOMATIC_REPAIR:
            raise ValueError(f"invalid option: {option}")

        changed = False
        for track in album.tracks:
            file = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / track.filename
            new_values: list[tuple[str, str | list[str] | None]] = []
            for tag_name in SINGLE_POSITIVE_NUMBER_TAGS:
                if tag_name in track.tags:
                    # gather all values for this tag that are numeric and > 0, if any
                    valid_values: set[str] = set()
                    for value in track.tags.get(tag_name, []):
                        if value.isdecimal() and int(value) > 0:
                            valid_values.add(value)
                    if not valid_values or len(valid_values) > 1:
                        # either there are no valid values or there's still more than one, deleting tag
                        new_value = None
                    else:
                        # there's only one value left that looks right, keep it
                        new_value = valid_values.pop()
                    if track.tags.get(tag_name) != (None if new_value is None else [new_value]):
                        new_values.append((tag_name, new_value))
            if new_values:
                self.ctx.console.print(f"setting {' and '.join(list(name for (name, _) in new_values))} on {track.filename}")
                set_basic_tags(file, new_values)
                changed = True

        return changed


def get_issues_invalid_disc_or_track_number(tracks: list[Track]):
    issues: set[str] = set()
    for track in tracks:
        if _has_multi_value(track.tags, SINGLE_POSITIVE_NUMBER_TAGS):
            issues.add("track/disc numbering tags with multiple values")
        if _has_non_numeric(track.tags, SINGLE_POSITIVE_NUMBER_TAGS):
            issues.add("track/disc numbering tags with non-numeric values")
        if _has_zero_value(track.tags, SINGLE_POSITIVE_NUMBER_TAGS):
            issues.add("track/disc numbering tags where the value is 0")
    return issues


def _has_multi_value(tags: dict[str, list[str]], tag_names: list[str]):
    for tag_name in tag_names:
        if len(tags.get(tag_name, [])) > 1:
            return True
    return False


def _has_non_numeric(tags: dict[str, list[str]], tag_names: list[str]):
    for tag_name in tag_names:
        for value in tags.get(tag_name, []):
            if not value.isdecimal():
                return True
    return False


def _has_zero_value(tags: dict[str, list[str]], tag_names: list[str]):
    for tag_name in tag_names:
        for value in tags.get(tag_name, []):
            if value.isdecimal() and int(value) == 0:
                return True
    return False
