from pathlib import Path

from albums.app import Context
from albums.types import Album, Track
from albums.checks.check_invalid_track_or_disc_number import CheckInvalidTrackOrDiscNumber


class TestCheckInvalidTrackOrDiscNumber:
    def test_all_valid(self):
        album = Album(
            "",
            [
                Track("1.flac", {}),  # missing is ok
                Track("2.flac", {"tracknumber": ["01"], "tracktotal": ["12"], "discnumber": ["01"], "disctotal": ["2"]}),
            ],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert not result

    def test_duplicate_value(self, mocker):
        album = Album(
            "",
            [Track("1.flac", {"tracknumber": ["1", "1"]})],  #  1 will be preserved
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckInvalidTrackOrDiscNumber(ctx).check(album)
        assert result
        assert "track/disc numbering tags with multiple values" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Automatically remove zero, non-numeric and multiple values"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch("albums.checks.check_invalid_track_or_disc_number.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[0].filename, [("tracknumber", "1")])

    def test_multiple_value(self, mocker):
        album = Album(
            "",
            [Track("1.flac", {"tracknumber": ["1", "2"]})],  # ambiguous will be deleted
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckInvalidTrackOrDiscNumber(ctx).check(album)
        assert result
        assert "track/disc numbering tags with multiple values" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Automatically remove zero, non-numeric and multiple values"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch("albums.checks.check_invalid_track_or_disc_number.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[0].filename, [("tracknumber", None)])

    def test_non_numeric_value(self, mocker):
        album = Album(
            "",
            [Track("1.flac", {"tracknumber": ["one"]})],
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckInvalidTrackOrDiscNumber(ctx).check(album)
        assert result
        assert "track/disc numbering tags with non-numeric values" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch("albums.checks.check_invalid_track_or_disc_number.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[0].filename, [("tracknumber", None)])

    def test_zero_value(self, mocker):
        album = Album(
            "",
            [Track("1.flac", {"tracknumber": ["0"]})],
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckInvalidTrackOrDiscNumber(ctx).check(album)
        assert result
        assert "track/disc numbering tags where the value is 0" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch("albums.checks.check_invalid_track_or_disc_number.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[0].filename, [("tracknumber", None)])

    def test_multiple_issues(self, mocker):
        album = Album(
            "",
            [
                Track("1.flac", {"tracknumber": ["1", "1"], "tracktotal": ["1", "2"], "discnumber": ["foo"], "disctotal": ["0"]}),
            ],
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckInvalidTrackOrDiscNumber(ctx).check(album)
        assert result
        assert "track/disc numbering tags with multiple values" in result.message
        assert "track/disc numbering tags with non-numeric values" in result.message
        assert "track/disc numbering tags where the value is 0" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch("albums.checks.check_invalid_track_or_disc_number.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (
            ctx.library_root / album.path / album.tracks[0].filename,
            [("tracknumber", "1"), ("tracktotal", None), ("discnumber", None), ("disctotal", None)],
        )
