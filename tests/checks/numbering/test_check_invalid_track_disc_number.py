from pathlib import Path

from albums.app import Context
from albums.checks.numbering.check_invalid_track_or_disc_number import CheckInvalidTrackOrDiscNumber
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import BasicTag
from albums.types import Album, Tag, Track


class TestCheckInvalidTrackOrDiscNumber:
    def test_all_valid(self):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac"),  # no tags is ok
                Track(
                    filename="2.flac",
                    tags=[
                        Tag(tag=BasicTag.TRACKNUMBER, value="01"),
                        Tag(tag=BasicTag.TRACKTOTAL, value="12"),
                        Tag(tag=BasicTag.DISCNUMBER, value="01"),
                        Tag(tag=BasicTag.DISCTOTAL, value="2"),
                    ],
                ),
            ],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert not result

    def test_duplicate_value(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tags=[Tag(tag=BasicTag.TRACKNUMBER, value="1"), Tag(tag=BasicTag.TRACKNUMBER, value="1")])
            ],  #  1 will be preserved
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert "track/disc numbering tags with multiple values" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Automatically remove zero, non-numeric and multiple values"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[0].filename, [(BasicTag.TRACKNUMBER, "1")])

    def test_multiple_value(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tags=[Tag(tag=BasicTag.TRACKNUMBER, value="1"), Tag(tag=BasicTag.TRACKNUMBER, value="2")])
            ],  # ambiguous will be deleted
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert "track/disc numbering tags with multiple values" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Automatically remove zero, non-numeric and multiple values"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[0].filename, [(BasicTag.TRACKNUMBER, None)])

    def test_non_numeric_value(self, mocker):
        album = Album(
            path="",
            tracks=[Track(filename="1.flac", tags=[Tag(tag=BasicTag.TRACKNUMBER, value="one")])],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert "track/disc numbering tags with non-numeric values" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[0].filename, [(BasicTag.TRACKNUMBER, None)])

    def test_zero_value(self, mocker):
        album = Album(
            path="",
            tracks=[Track(filename="1.flac", tags=[Tag(tag=BasicTag.TRACKNUMBER, value="0")])],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert "track/disc numbering tags where the value is 0" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[0].filename, [(BasicTag.TRACKNUMBER, None)])

    def test_multiple_issues(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    tags=[
                        Tag(tag=BasicTag.TRACKNUMBER, value="1"),
                        Tag(tag=BasicTag.TRACKNUMBER, value="1"),
                        Tag(tag=BasicTag.TRACKTOTAL, value="1"),
                        Tag(tag=BasicTag.TRACKTOTAL, value="2"),
                        Tag(tag=BasicTag.DISCNUMBER, value="foo"),
                        Tag(tag=BasicTag.DISCTOTAL, value="0"),
                    ],
                ),
            ],
        )
        result = CheckInvalidTrackOrDiscNumber(Context()).check(album)
        assert result
        assert "track/disc numbering tags with multiple values" in result.message
        assert "track/disc numbering tags with non-numeric values" in result.message
        assert "track/disc numbering tags where the value is 0" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[0].filename,
            [(BasicTag.TRACKNUMBER, "1"), (BasicTag.TRACKTOTAL, None), (BasicTag.DISCNUMBER, None), (BasicTag.DISCTOTAL, None)],
        )
