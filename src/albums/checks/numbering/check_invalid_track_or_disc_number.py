import logging
from dataclasses import dataclass
from typing import Final, Mapping, Sequence

from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.checks.helpers import format_field_values, ordered_tracks
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField, Cap
from albums.words import plural

logger: Final = logging.getLogger(__name__)

OPTION_AUTOMATIC_REPAIR: Final = ">> Automatically remove zero, non-numeric and multiple values"
SINGLE_POSITIVE_NUMBER_FIELDS: Final = [BasicField.TRACKNUMBER, BasicField.TRACKTOTAL, BasicField.DISCNUMBER, BasicField.DISCTOTAL]

PROBLEM_MULTIPLE_VALUES: Final = "multiple values"
PROBLEM_NON_NUMERIC_VALUES: Final = "non-numeric values"
PROBLEM_ZERO_VALUE: Final = "value is 0"
PROBLEM_ORDER: Final = [PROBLEM_MULTIPLE_VALUES, PROBLEM_NON_NUMERIC_VALUES, PROBLEM_ZERO_VALUE]


@dataclass(frozen=True)
class NumberFieldPlan:
    """Problems found in one track's number field and the automatic fix planned for it.

    Attributes:
        problems: Descriptions of the problems found; empty when the field is absent or has a single positive number.
        new_value: The value the fix will write to the field; ``None`` means the fix will delete the field.
        changed: Whether the fix will modify the field at all.
    """

    problems: tuple[str, ...]
    new_value: str | None
    changed: bool

    @staticmethod
    def of(values: Sequence[str]) -> "NumberFieldPlan":
        problems: list[str] = []
        if len(values) > 1:
            problems.append(PROBLEM_MULTIPLE_VALUES)
        if any(not value.isdecimal() for value in values):
            problems.append(PROBLEM_NON_NUMERIC_VALUES)
        if any(value.isdecimal() and int(value) == 0 for value in values):
            problems.append(PROBLEM_ZERO_VALUE)
        if not problems:
            return NumberFieldPlan((), None, False)
        valid_values = {int(value) for value in values if value.isdecimal() and int(value) > 0}
        if len(valid_values) == 1:
            # exactly one unique number remains, keep it without leading zeros
            return NumberFieldPlan(tuple(problems), str(valid_values.pop()), True)
        return NumberFieldPlan(tuple(problems), None, True)


class CheckInvalidTrackOrDiscNumber(Check):
    name = "invalid-track-or-disc-number"
    default_config = {"enabled": True}
    must_pass_checks = {"disc-in-track-number"}

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.FORMATTED_TRACK_NUMBER) for track in album.tracks):
            return None  # not valid if track number is not supported or is stored as an integer

        field_problems: dict[BasicField, set[str]] = {}
        affected_tracks = 0
        for track in album.tracks:
            track_has_problems = False
            for field in SINGLE_POSITIVE_NUMBER_FIELDS:
                plan = NumberFieldPlan.of(track.get(field, default=[]))
                if plan.problems:
                    track_has_problems = True
                    field_problems.setdefault(field, set()).update(plan.problems)
            affected_tracks += track_has_problems

        if not field_problems:
            return None

        message = f"bad values in track/disc number fields: {self._describe_field_problems(field_problems)} on {plural(affected_tracks, 'track')}"
        table = (
            ["filename", *[field.value for field in SINGLE_POSITIVE_NUMBER_FIELDS]],
            [self._table_row(track) for track in ordered_tracks(album)],
        )
        option_free_text = False
        option_automatic_index = 0
        return CheckResult(
            message,
            Fixer(
                lambda option: self._fix(album, option),
                [OPTION_AUTOMATIC_REPAIR],
                option_free_text,
                option_automatic_index,
                table,
                f"select option to fix {plural(affected_tracks, 'track')}",
            ),
        )

    def _fix(self, album: Album, option: str):
        if option != OPTION_AUTOMATIC_REPAIR:
            raise ValueError(f"invalid option: {option}")

        changed = False
        for track in album.tracks:
            file = self.ctx.config.library / album.path / track.filename
            new_values: list[tuple[BasicField, str | None]] = []
            for field in SINGLE_POSITIVE_NUMBER_FIELDS:
                plan = NumberFieldPlan.of(track.get(field, default=[]))
                if plan.changed:
                    new_values.append((field, plan.new_value))
                    if plan.new_value is None:
                        self.ctx.console.print(f"removing {field.value} from {escape(track.filename)}", highlight=False)
                    else:
                        self.ctx.console.print(f"setting {field.value} to {plan.new_value} on {escape(track.filename)}", highlight=False)
            if new_values:
                self.tagger.get(album.path).set_basic_fields(file, new_values)
                changed = True

        return FixResult.of(changed)

    @staticmethod
    def _describe_field_problems(field_problems: Mapping[BasicField, set[str]]) -> str:
        descriptions: list[str] = []
        for field in SINGLE_POSITIVE_NUMBER_FIELDS:
            if field in field_problems:
                problems = sorted(field_problems[field], key=PROBLEM_ORDER.index)
                descriptions.append(f"{field.value} ({', '.join(problems)})")
        return ", ".join(descriptions)

    @staticmethod
    def _table_row(track: Track) -> list[str]:
        row: list[str] = [escape(track.filename)]
        for field in SINGLE_POSITIVE_NUMBER_FIELDS:
            values = track.get(field, default=[])
            if not values:
                row.append(format_field_values(None))
                continue
            plan = NumberFieldPlan.of(values)
            if not plan.changed:
                row.append(format_field_values(values))
            elif plan.new_value is None:
                row.append(f"[red]{escape(', '.join(values))} -> removed[/red]")
            else:
                row.append(f"[yellow]{escape(', '.join(values))} -> {escape(plan.new_value)}[/yellow]")
        return row
