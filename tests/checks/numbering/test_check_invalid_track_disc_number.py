from pathlib import Path
from typing import Iterable
from unittest.mock import call

import pytest
from rich.console import RenderableType
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.check_types import CheckResult, FixResult
from albums.checks.numbering.check_invalid_track_or_disc_number import (
    PROBLEM_MULTIPLE_VALUES,
    PROBLEM_NON_NUMERIC_VALUES,
    PROBLEM_ZERO_VALUE,
    CheckInvalidTrackOrDiscNumber,
    NumberFieldPlan,
)
from albums.database import MEMORY, db_open
from albums.entities import Album, Track
from albums.interactive.interact import interact
from albums.tagger import AlbumTagger, BasicField

NONE_CELL = "[bold italic]None[/bold italic]"
TABLE_HEADERS = ["filename", "tracknumber", "tracktotal", "discnumber", "disctotal"]


def fixer_table(result: CheckResult) -> tuple[Iterable[str], Iterable[Iterable[RenderableType]]]:
    table = result.fixer.get_table()
    assert table is not None
    return table


def apply_automatic_fix(result: CheckResult) -> FixResult:
    fixer = result.fixer
    assert fixer is not None
    index = fixer.option_automatic_index
    assert index is not None
    return fixer.fix(fixer.options[index])


class TestNumberFieldPlan:
    @pytest.mark.parametrize(
        ("values", "plan"),
        [
            ([], NumberFieldPlan((), None, False)),  # absent field is fine
            (["1"], NumberFieldPlan((), None, False)),  # single positive number is fine
            (["01"], NumberFieldPlan((), None, False)),  # leading zeros are fine
            (["0"], NumberFieldPlan((PROBLEM_ZERO_VALUE,), None, True)),
            (["x"], NumberFieldPlan((PROBLEM_NON_NUMERIC_VALUES,), None, True)),
            (["1", "1"], NumberFieldPlan((PROBLEM_MULTIPLE_VALUES,), "1", True)),
            (["9", "09"], NumberFieldPlan((PROBLEM_MULTIPLE_VALUES,), "9", True)),  # same number, keep without leading zeros
            (["09", "9"], NumberFieldPlan((PROBLEM_MULTIPLE_VALUES,), "9", True)),  # order does not matter
            (["01", "1"], NumberFieldPlan((PROBLEM_MULTIPLE_VALUES,), "1", True)),
            (["1", "2"], NumberFieldPlan((PROBLEM_MULTIPLE_VALUES,), None, True)),  # ambiguous, remove
            (["0", "1"], NumberFieldPlan((PROBLEM_MULTIPLE_VALUES, PROBLEM_ZERO_VALUE), "1", True)),
            (["x", "7"], NumberFieldPlan((PROBLEM_MULTIPLE_VALUES, PROBLEM_NON_NUMERIC_VALUES), "7", True)),
            (["0", "0"], NumberFieldPlan((PROBLEM_MULTIPLE_VALUES, PROBLEM_ZERO_VALUE), None, True)),
            (["0", "x"], NumberFieldPlan((PROBLEM_MULTIPLE_VALUES, PROBLEM_NON_NUMERIC_VALUES, PROBLEM_ZERO_VALUE), None, True)),
            (["1", "0", "x"], NumberFieldPlan((PROBLEM_MULTIPLE_VALUES, PROBLEM_NON_NUMERIC_VALUES, PROBLEM_ZERO_VALUE), "1", True)),
        ],
    )
    def test_plan(self, values, plan):
        assert NumberFieldPlan.of(values) == plan


class TestCheckInvalidTrackOrDiscNumber:
    def test_all_valid(self):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac"),  # no tags is ok
                Track(
                    filename="2.flac",
                    tag={BasicField.TRACKNUMBER: "01", BasicField.TRACKTOTAL: "12", BasicField.DISCNUMBER: "01", BasicField.DISCTOTAL: "2"},
                ),
            ],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert not result

    def test_unsupported_track_number_format(self):
        album = Album(path="", tracks=[Track(filename="1.m4a", tag={BasicField.TRACKTOTAL: ["9", "09"]})])
        assert CheckInvalidTrackOrDiscNumber(Context()).check(album) is None

    def test_duplicate_values_are_kept(self, mocker):
        album = Album(path="", tracks=[Track(filename="1.flac", tag={BasicField.TRACKNUMBER: ["1", "1"]})])
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert result.message == "bad values in track/disc number fields: tracknumber (multiple values) on 1 track"
        assert result.fixer
        assert result.fixer.options == [">> Automatically remove zero, non-numeric and multiple values"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.prompt == "select option to fix 1 track"
        (headers, rows) = fixer_table(result)
        assert headers == TABLE_HEADERS
        assert rows == [["1.flac", "[yellow]1, 1 -> 1[/yellow]", NONE_CELL, NONE_CELL, NONE_CELL]]

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        mock_set_basic_fields.assert_called_once_with(Path(album.path) / "1.flac", [(BasicField.TRACKNUMBER, "1")])

    def test_tracktotal_9_and_09(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicField.TRACKNUMBER: "1", BasicField.TRACKTOTAL: ["9", "09"]}),  # will be set to 9
                Track(filename="2.flac", tag={BasicField.TRACKNUMBER: "2", BasicField.TRACKTOTAL: "9"}),  # valid
            ],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert result.message == "bad values in track/disc number fields: tracktotal (multiple values) on 1 track"
        assert result.fixer
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.prompt == "select option to fix 1 track"
        (headers, rows) = fixer_table(result)
        assert headers == TABLE_HEADERS
        # all tracks are listed, only the bad value is marked
        assert rows == [
            ["1.flac", "1", "[yellow]9, 09 -> 9[/yellow]", NONE_CELL, NONE_CELL],
            ["2.flac", "2", "9", NONE_CELL, NONE_CELL],
        ]

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        mock_set_basic_fields.assert_called_once_with(Path(album.path) / "1.flac", [(BasicField.TRACKTOTAL, "9")])

    def test_multiple_distinct_values_are_removed(self, mocker):
        album = Album(path="", tracks=[Track(filename="1.flac", tag={BasicField.TRACKNUMBER: ["1", "2"]})])  # ambiguous will be deleted
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert result.message == "bad values in track/disc number fields: tracknumber (multiple values) on 1 track"
        assert result.fixer
        (headers, rows) = fixer_table(result)
        assert headers == TABLE_HEADERS
        assert rows == [["1.flac", "[red]1, 2 -> removed[/red]", NONE_CELL, NONE_CELL, NONE_CELL]]

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        mock_set_basic_fields.assert_called_once_with(Path(album.path) / "1.flac", [(BasicField.TRACKNUMBER, None)])

    def test_non_numeric_value_is_removed(self, mocker):
        album = Album(path="", tracks=[Track(filename="1.flac", tag={BasicField.TRACKNUMBER: "one"})])
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert result.message == "bad values in track/disc number fields: tracknumber (non-numeric values) on 1 track"
        assert result.fixer
        (headers, rows) = fixer_table(result)
        assert rows == [["1.flac", "[red]one -> removed[/red]", NONE_CELL, NONE_CELL, NONE_CELL]]

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        mock_set_basic_fields.assert_called_once_with(Path(album.path) / "1.flac", [(BasicField.TRACKNUMBER, None)])

    def test_zero_value_is_removed(self, mocker):
        album = Album(path="", tracks=[Track(filename="1.flac", tag={BasicField.TRACKNUMBER: "0"})])
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert result.message == "bad values in track/disc number fields: tracknumber (value is 0) on 1 track"
        assert result.fixer
        (headers, rows) = fixer_table(result)
        assert rows == [["1.flac", "[red]0 -> removed[/red]", NONE_CELL, NONE_CELL, NONE_CELL]]

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        mock_set_basic_fields.assert_called_once_with(Path(album.path) / "1.flac", [(BasicField.TRACKNUMBER, None)])

    def test_mixed_invalid_values_keep_unique_number(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicField.TRACKNUMBER: ["0", "1"]}),  # 1 will be kept
                Track(filename="2.flac", tag={BasicField.TRACKTOTAL: ["x", "7"]}),  # 7 will be kept
            ],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert (
            result.message
            == "bad values in track/disc number fields: tracknumber (multiple values, value is 0), tracktotal (multiple values, non-numeric values) on 2 tracks"
        )
        assert result.fixer
        assert result.fixer.prompt == "select option to fix 2 tracks"
        (headers, rows) = fixer_table(result)
        assert headers == TABLE_HEADERS
        assert rows == [
            ["1.flac", "[yellow]0, 1 -> 1[/yellow]", NONE_CELL, NONE_CELL, NONE_CELL],
            ["2.flac", NONE_CELL, "[yellow]x, 7 -> 7[/yellow]", NONE_CELL, NONE_CELL],
        ]

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_basic_fields.call_args_list == [
            call(Path(album.path) / "1.flac", [(BasicField.TRACKNUMBER, "1")]),
            call(Path(album.path) / "2.flac", [(BasicField.TRACKTOTAL, "7")]),
        ]

    def test_all_fields_bad_on_one_track(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    tag={
                        BasicField.TRACKNUMBER: ["1", "1"],  # 1 will be kept
                        BasicField.TRACKTOTAL: ["9", "09"],  # 9 will be kept
                        BasicField.DISCNUMBER: "foo",  # removed
                        BasicField.DISCTOTAL: "0",  # removed
                    },
                ),
            ],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert (
            result.message == "bad values in track/disc number fields: tracknumber (multiple values), tracktotal (multiple values), "
            "discnumber (non-numeric values), disctotal (value is 0) on 1 track"
        )
        assert result.fixer
        (headers, rows) = fixer_table(result)
        assert headers == TABLE_HEADERS
        assert rows == [
            ["1.flac", "[yellow]1, 1 -> 1[/yellow]", "[yellow]9, 09 -> 9[/yellow]", "[red]foo -> removed[/red]", "[red]0 -> removed[/red]"]
        ]

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        mock_set_basic_fields.assert_called_once_with(
            Path(album.path) / "1.flac",
            [(BasicField.TRACKNUMBER, "1"), (BasicField.TRACKTOTAL, "9"), (BasicField.DISCNUMBER, None), (BasicField.DISCTOTAL, None)],
        )

    def test_table_lists_all_tracks_in_playback_order(self):
        album = Album(
            path="",
            tracks=[
                Track(filename="2.b.flac", tag={BasicField.TRACKNUMBER: "2", BasicField.TRACKTOTAL: ["9", "09"]}),
                Track(filename="1.a.flac", tag={BasicField.TRACKNUMBER: "1"}),
                Track(filename="3.c.flac", tag={BasicField.TRACKNUMBER: "3", BasicField.DISCTOTAL: "2"}),
            ],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert result.fixer
        (headers, rows) = fixer_table(result)
        assert headers == TABLE_HEADERS
        assert rows == [
            ["1.a.flac", "1", NONE_CELL, NONE_CELL, NONE_CELL],
            ["2.b.flac", "2", "[yellow]9, 09 -> 9[/yellow]", NONE_CELL, NONE_CELL],
            ["3.c.flac", "3", NONE_CELL, NONE_CELL, "2"],
        ]

    def test_unaffected_tracks_are_not_modified(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicField.TRACKNUMBER: ["1", "2"]}),  # ambiguous will be deleted
                Track(filename="2.flac"),  # no number fields at all, leave alone
            ],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert result.message == "bad values in track/disc number fields: tracknumber (multiple values) on 1 track"
        assert result.fixer

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        mock_set_basic_fields.assert_called_once_with(Path(album.path) / "1.flac", [(BasicField.TRACKNUMBER, None)])

    def test_invalid_option_raises(self):
        album = Album(path="", tracks=[Track(filename="1.flac", tag={BasicField.TRACKNUMBER: "0"})])
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert result.fixer
        with pytest.raises(ValueError):
            result.fixer.fix("not a valid option")


class TestCheckInvalidTrackOrDiscNumberInteractive:
    def test_interactive_fix(self, mocker):
        album = Album(
            path="foo",
            tracks=[Track(filename="1.flac", tag={BasicField.TRACKNUMBER: "1", BasicField.TRACKTOTAL: ["9", "09"]})],
        )
        ctx = Context()
        ctx.db = db_open(MEMORY)
        try:
            result = CheckInvalidTrackOrDiscNumber(ctx).check(album)
            assert result
            assert result.fixer
            mock_choice = mocker.patch("albums.interactive.interact.choice", return_value=result.fixer.options[0])
            mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")

            with Session(ctx.db) as session:
                (changed, deleted, quit) = interact(ctx, session, CheckInvalidTrackOrDiscNumber.name, result, album, True)
                assert changed
                assert not deleted
                assert not quit
                assert mock_choice.call_count == 1
                mock_set_basic_fields.assert_called_once_with(Path("foo/1.flac"), [(BasicField.TRACKTOTAL, "9")])
        finally:
            ctx.db.dispose()
