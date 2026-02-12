import os
from pathlib import Path

from albums.app import Context
from albums.checks.check_disc_in_track_number import CheckDiscInTrackNumber
from albums.types import Album, Track


class TestCheckDiscInTrackNumber:
    def test_check_track_number_disc_in_tracknumber_ok(self, mocker):
        album = Album(
            "foo" + os.sep,
            [
                Track("1-1.flac", {"tracknumber": ["1"], "discnumber": ["1"]}),
                Track("1-2.flac", {"tracknumber": ["2"], "discnumber": ["1"]}),
                Track("2-1.flac", {"tracknumber": ["1"], "discnumber": ["2"]}),
            ],
        )
        result = CheckDiscInTrackNumber(Context()).check(album)
        assert result is None

    def test_check_track_number_disc_in_tracknumber_unfixable(self, mocker):
        album = Album(
            "foo" + os.sep,
            [
                Track("1-1.flac", {"tracknumber": ["1-1"], "discnumber": ["1"]}),
                Track("1-2.flac", {"tracknumber": ["1-2"], "discnumber": ["1"]}),
                Track("2-1.flac", {"tracknumber": ["2-1"], "discnumber": ["2"]}),
            ],
        )
        result = CheckDiscInTrackNumber(Context()).check(album)
        assert result is None

    def test_check_track_number_disc_in_tracknumber(self, mocker):
        album = Album(
            "foo" + os.sep,
            [
                Track("1-1.flac", {"tracknumber": ["1-1"]}),
                Track("1-2.flac", {"tracknumber": ["1-2"]}),
                Track("2-1.flac", {"tracknumber": ["2-1"]}),
            ],
        )
        result = CheckDiscInTrackNumber(Context()).check(album)
        assert "track numbers formatted as number-dash-number, probably discnumber and tracknumber" in result.message
        fixer = result.fixer
        assert fixer
        assert fixer.options == [">> Split track number into disc number and track number"]
        assert fixer.option_automatic_index == 0
        mock_set_basic_tags = mocker.patch("albums.checks.check_disc_in_track_number.set_basic_tags")
        assert fixer.fix(fixer.options[fixer.option_automatic_index])
        assert mock_set_basic_tags.call_count == 3
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[2].filename,
            [("discnumber", "2"), ("tracknumber", "1")],
        )
