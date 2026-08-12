from pathlib import Path

from albums.app import Context
from albums.checks.numbering.check_invalid_track_or_disc_number import CheckInvalidTrackOrDiscNumber
from albums.entities import Album, Track
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import BasicField


class TestCheckInvalidTrackOrDiscNumber:
    def test_all_valid(self):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac"),  # no tag is ok
                Track(
                    filename="2.flac",
                    tag={BasicField.TRACKNUMBER: "01", BasicField.TRACKTOTAL: "12", BasicField.DISCNUMBER: "01", BasicField.DISCTOTAL: "2"},
                ),
            ],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert not result

    def test_duplicate_value(self, mocker):
        album = Album(
            path="",
            tracks=[Track(filename="1.flac", tag={BasicField.TRACKNUMBER: ["1", "1"]})],  #  1 will be preserved
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert "track/disc numbering fields with multiple values" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Automatically remove zero, non-numeric and multiple values"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_fields.call_count == 1
        assert mock_set_basic_fields.call_args.args == (Path(album.path) / album.tracks[0].filename, [(BasicField.TRACKNUMBER, "1")])

    def test_multiple_value(self, mocker):
        album = Album(
            path="",
            tracks=[Track(filename="1.flac", tag={BasicField.TRACKNUMBER: ["1", "2"]})],  # ambiguous will be deleted
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert "track/disc numbering fields with multiple values" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Automatically remove zero, non-numeric and multiple values"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_fields.call_count == 1
        assert mock_set_basic_fields.call_args.args == (Path(album.path) / album.tracks[0].filename, [(BasicField.TRACKNUMBER, None)])

    def test_non_numeric_value(self, mocker):
        album = Album(path="", tracks=[Track(filename="1.flac", tag={BasicField.TRACKNUMBER: "one"})])
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert "track/disc numbering fields with non-numeric values" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_fields.call_count == 1
        assert mock_set_basic_fields.call_args.args == (Path(album.path) / album.tracks[0].filename, [(BasicField.TRACKNUMBER, None)])

    def test_zero_value(self, mocker):
        album = Album(path="", tracks=[Track(filename="1.flac", tag={BasicField.TRACKNUMBER: "0"})])
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert "track/disc numbering fields where the value is 0" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_fields.call_count == 1
        assert mock_set_basic_fields.call_args.args == (Path(album.path) / album.tracks[0].filename, [(BasicField.TRACKNUMBER, None)])

    def test_multiple_issues(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    tag={
                        BasicField.TRACKNUMBER: ["1", "1"],
                        BasicField.TRACKTOTAL: ["1", "2"],
                        BasicField.DISCNUMBER: "foo",
                        BasicField.DISCTOTAL: "0",
                    },
                ),
            ],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert "track/disc numbering fields with multiple values" in result.message
        assert "track/disc numbering fields with non-numeric values" in result.message
        assert "track/disc numbering fields where the value is 0" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_fields.call_count == 1
        assert mock_set_basic_fields.call_args.args == (
            Path(album.path) / album.tracks[0].filename,
            [(BasicField.TRACKNUMBER, "1"), (BasicField.TRACKTOTAL, None), (BasicField.DISCNUMBER, None), (BasicField.DISCTOTAL, None)],
        )
