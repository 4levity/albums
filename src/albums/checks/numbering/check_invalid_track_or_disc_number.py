import logging
from typing import Collection, Final, Mapping, Sequence

from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField, Cap

from .check_track_numbering import describe_track_number, ordered_tracks

logger: Final = logging.getLogger(__name__)

OPTION_AUTOMATIC_REPAIR: Final = ">> Automatically remove zero, non-numeric and multiple values"
SINGLE_POSITIVE_NUMBER_FIELDS: Final = [BasicField.TRACKNUMBER, BasicField.TRACKTOTAL, BasicField.DISCNUMBER, BasicField.DISCTOTAL]


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
                f"bad values in track/disc number fields: {', '.join(issues)}",
                Fixer(
                    lambda option: self._fix(album, option),
                    [OPTION_AUTOMATIC_REPAIR],
                    option_free_text,
                    option_automatic_index,
                    (["track", "filename"], [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)]),
                ),
            )

        return None

    def _fix(self, album: Album, option: str):
        if option != OPTION_AUTOMATIC_REPAIR:
            raise ValueError(f"invalid option: {option}")

        changed = False
        for track in album.tracks:
            file = self.ctx.config.library / album.path / track.filename
            new_values: list[tuple[BasicField, str | list[str] | None]] = []
            for field in SINGLE_POSITIVE_NUMBER_FIELDS:
                track_fields = track.field_dict()
                if field in track_fields:
                    # gather all values for this field that are numeric and > 0, if any
                    valid_values: set[str] = set()
                    for value in track_fields.get(field, []):
                        if value.isdecimal() and int(value) > 0:
                            valid_values.add(value)
                    if not valid_values or len(valid_values) > 1:
                        # either there are no valid values or there's still more than one, deleting field
                        new_value = None
                    else:
                        # there's only one value left that looks right, keep it
                        new_value = valid_values.pop()
                    if track_fields.get(field) != (None if new_value is None else [new_value]):
                        new_values.append((field, new_value))
            if new_values:
                self.ctx.console.print(f"setting {' and '.join(list(name for (name, _) in new_values))} on {escape(track.filename)}", highlight=False)
                self.tagger.get(album.path).set_basic_fields(file, new_values)
                changed = True

        return FixResult.of(changed)


def get_issues_invalid_disc_or_track_number(tracks: Sequence[Track]):
    issues: set[str] = set()
    for track in tracks:
        track_fields = track.field_dict()
        if _has_multi_value(track_fields, SINGLE_POSITIVE_NUMBER_FIELDS):
            issues.add("track/disc numbering fields with multiple values")
        if _has_non_numeric(track_fields, SINGLE_POSITIVE_NUMBER_FIELDS):
            issues.add("track/disc numbering fields with non-numeric values")
        if _has_zero_value(track_fields, SINGLE_POSITIVE_NUMBER_FIELDS):
            issues.add("track/disc numbering fields where the value is 0")
    return issues


def _has_multi_value(fields: Mapping[BasicField, Sequence[str]], check_fields: Collection[BasicField]):
    for field_name in check_fields:
        if len(fields.get(field_name, [])) > 1:
            return True
    return False


def _has_non_numeric(fields: Mapping[BasicField, Sequence[str]], check_fields: Collection[BasicField]):
    for field_name in check_fields:
        for value in fields.get(field_name, []):
            if not value.isdecimal():
                return True
    return False


def _has_zero_value(fields: Mapping[BasicField, Sequence[str]], check_fields: Collection[BasicField]):
    for field_name in check_fields:
        for value in fields.get(field_name, []):
            if value.isdecimal() and int(value) == 0:
                return True
    return False
