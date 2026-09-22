from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.check_types import FixResult
from albums.checks.numbering.check_zero_pad_numbers import CheckZeroPadNumbers
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField

from ...helpers import apply_automatic_fix


class TestZeroPadNumbers:
    def test_check_pad_track_if_needed(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", fields={BasicField.TRACKNUMBER: "1"}),
                Track(filename="2.flac", fields={BasicField.TRACKNUMBER: "2"}),
                Track(filename="3.flac", fields={BasicField.TRACKNUMBER: "3"}),
                Track(filename="4.flac", fields={BasicField.TRACKNUMBER: "4"}),
                Track(filename="5.flac", fields={BasicField.TRACKNUMBER: "5"}),
                Track(filename="6.flac", fields={BasicField.TRACKNUMBER: "6"}),
                Track(filename="7.flac", fields={BasicField.TRACKNUMBER: "7"}),
                Track(filename="8.flac", fields={BasicField.TRACKNUMBER: "8"}),
                Track(filename="9.flac", fields={BasicField.TRACKNUMBER: "9"}),
                Track(filename="10.flac", fields={BasicField.TRACKNUMBER: "10"}),
            ],
        )
        ctx = Context()
        ctx.config.checks = {
            "zero-pad-numbers": {
                "enabled": True,
                "tracknumber_pad": "if_needed",
            }
        }
        result = CheckZeroPadNumbers(ctx).check(album)
        assert "incorrect zero padding for 9 track numbers" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Apply policy: tracknumber pad IF_NEEDED"]
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_basic_fields.call_args_list == [
            call(Path(album.path) / album.tracks[0].filename, [(BasicField.TRACKNUMBER, "01")]),
            call(Path(album.path) / album.tracks[1].filename, [(BasicField.TRACKNUMBER, "02")]),
            call(Path(album.path) / album.tracks[2].filename, [(BasicField.TRACKNUMBER, "03")]),
            call(Path(album.path) / album.tracks[3].filename, [(BasicField.TRACKNUMBER, "04")]),
            call(Path(album.path) / album.tracks[4].filename, [(BasicField.TRACKNUMBER, "05")]),
            call(Path(album.path) / album.tracks[5].filename, [(BasicField.TRACKNUMBER, "06")]),
            call(Path(album.path) / album.tracks[6].filename, [(BasicField.TRACKNUMBER, "07")]),
            call(Path(album.path) / album.tracks[7].filename, [(BasicField.TRACKNUMBER, "08")]),
            call(Path(album.path) / album.tracks[8].filename, [(BasicField.TRACKNUMBER, "09")]),
        ]

    def test_check_pad_remove_all_unnecessary(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    fields={
                        BasicField.TRACKNUMBER: "01",
                        BasicField.TRACKTOTAL: "02",
                        BasicField.DISCNUMBER: "01",
                        BasicField.DISCTOTAL: "01",
                    },
                ),
                Track(
                    filename="2.flac",
                    fields={
                        BasicField.TRACKNUMBER: "02",
                        BasicField.TRACKTOTAL: "02",
                        BasicField.DISCNUMBER: "01",
                        BasicField.DISCTOTAL: "01",
                    },
                ),
            ],
        )
        ctx = Context()
        ctx.config.checks = {
            "zero-pad-numbers": {
                "enabled": True,
                "tracknumber_pad": "if_needed",
                "tracktotal_pad": "never",
                "discnumber_pad": "if_needed",
                "disctotal_pad": "never",
            }
        }
        result = CheckZeroPadNumbers(ctx).check(album)
        assert "incorrect zero padding for 2 disc numbers and 2 disc totals and 2 track numbers and 2 track totals" in result.message
        assert result.fixer
        assert result.fixer.options == [
            ">> Apply policy: discnumber pad IF_NEEDED and disctotal pad NEVER and tracknumber pad IF_NEEDED and tracktotal pad NEVER"
        ]
        assert result.fixer.table
        # the table shows current values and highlights (yellow) the values that will change
        (headers, rows) = result.fixer.get_table() or ([], [])
        assert list(headers) == ["track", "filename", "tracknumber", "tracktotal", "discnumber", "disctotal"]
        assert [list(row) for row in rows] == [
            [
                "(disc 01/01) 01/02",
                "1.flac",
                "[yellow]01 -> 1[/yellow]",
                "[yellow]02 -> 2[/yellow]",
                "[yellow]01 -> 1[/yellow]",
                "[yellow]01 -> 1[/yellow]",
            ],
            [
                "(disc 01/01) 02/02",
                "2.flac",
                "[yellow]02 -> 2[/yellow]",
                "[yellow]02 -> 2[/yellow]",
                "[yellow]01 -> 1[/yellow]",
                "[yellow]01 -> 1[/yellow]",
            ],
        ]

        # automatically fixed
        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_basic_fields.call_args_list == [
            call(
                Path(album.path) / album.tracks[0].filename,
                [(BasicField.TRACKNUMBER, "1"), (BasicField.TRACKTOTAL, "2"), (BasicField.DISCNUMBER, "1"), (BasicField.DISCTOTAL, "1")],
            ),
            call(
                Path(album.path) / album.tracks[1].filename,
                [(BasicField.TRACKNUMBER, "2"), (BasicField.TRACKTOTAL, "2"), (BasicField.DISCNUMBER, "1"), (BasicField.DISCTOTAL, "1")],
            ),
        ]

    def test_check_pad_tracknumber_and_discnumber_if_needed(self, mocker):
        album = Album(path="a")
        for discnumber in range(1, 11):
            for tracknumber in range(1, 11):
                album.tracks.append(
                    Track(
                        filename=f"{discnumber}-{tracknumber}.flac",
                        fields={
                            BasicField.DISCNUMBER: str(discnumber),
                            BasicField.TRACKNUMBER: str(tracknumber),
                        },
                    )
                )
        assert len(album.tracks) == 100
        ctx = Context()
        ctx.config.checks = {
            "zero-pad-numbers": {
                "enabled": True,
                "tracknumber_pad": "if_needed",
                "discnumber_pad": "if_needed",
            }
        }
        result = CheckZeroPadNumbers(ctx).check(album)
        assert "incorrect zero padding for 90 disc numbers and 90 track numbers" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Apply policy: discnumber pad IF_NEEDED and tracknumber pad IF_NEEDED"]
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        # discs 1-9: tracks 1-9 get tracknumber and discnumber padded, track 10 gets only discnumber padded;
        # disc 10: tracks 1-9 get tracknumber padded, track 10 needs no change (99 calls total)
        expected_calls = []
        for disc in range(1, 11):
            for track in range(1, 11):
                new_values = []
                if track < 10:
                    new_values.append((BasicField.TRACKNUMBER, f"{track:02d}"))
                if disc < 10:
                    new_values.append((BasicField.DISCNUMBER, f"{disc:02d}"))
                if new_values:
                    expected_calls.append(call(Path(album.path) / f"{disc}-{track}.flac", new_values))
        assert mock_set_basic_fields.call_args_list == expected_calls

    def test_check_pad_two_digit_minimum(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    fields={
                        BasicField.TRACKNUMBER: "01",
                        BasicField.TRACKTOTAL: "2",
                        BasicField.DISCNUMBER: "01",
                        BasicField.DISCTOTAL: "1",
                    },
                ),
                Track(
                    filename="2.flac",
                    fields={
                        BasicField.TRACKNUMBER: "2",
                        BasicField.TRACKTOTAL: "2",
                        BasicField.DISCNUMBER: "1",
                        BasicField.DISCTOTAL: "1",
                    },
                ),
            ],
        )
        ctx = Context()
        ctx.config.checks = {
            "zero-pad-numbers": {
                "enabled": True,
                "tracknumber_pad": "TWO_DIGIT_MINIMUM",
                "tracktotal_pad": "TWO_DIGIT_MINIMUM",
                "discnumber_pad": "two_digit_minimum",
                "disctotal_pad": "two_digit_minimum",
            }
        }
        result = CheckZeroPadNumbers(ctx).check(album)
        assert "incorrect zero padding for 1 disc numbers and 2 disc totals and 1 track numbers and 2 track totals" in result.message
        assert result.fixer
        assert result.fixer.options == [
            ">> Apply policy: discnumber pad TWO_DIGIT_MINIMUM and disctotal pad TWO_DIGIT_MINIMUM and tracknumber pad TWO_DIGIT_MINIMUM and tracktotal pad TWO_DIGIT_MINIMUM"
        ]
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_basic_fields.call_args_list == [
            call(Path(album.path) / album.tracks[0].filename, [(BasicField.TRACKTOTAL, "02"), (BasicField.DISCTOTAL, "01")]),
            call(
                Path(album.path) / album.tracks[1].filename,
                [(BasicField.TRACKNUMBER, "02"), (BasicField.TRACKTOTAL, "02"), (BasicField.DISCNUMBER, "01"), (BasicField.DISCTOTAL, "01")],
            ),
        ]

    def test_check_pad_with_id3(self, mocker):
        album = Album(path="", tracks=[Track(filename="1.mp3", fields={BasicField.TRACKNUMBER: "01", BasicField.TRACKTOTAL: "2"})])
        ctx = Context()
        ctx.config.checks = {
            "zero-pad-numbers": {
                "enabled": True,
                "tracknumber_pad": "if_needed",
                "tracktotal_pad": "never",
                "discnumber_pad": "never",
                "disctotal_pad": "never",
            }
        }
        result = CheckZeroPadNumbers(ctx).check(album)
        assert "incorrect zero padding for 1 track numbers" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Apply policy: tracknumber pad IF_NEEDED"]
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_basic_fields.call_args.args == (Path(album.path) / album.tracks[0].filename, [(BasicField.TRACKNUMBER, "1")])
