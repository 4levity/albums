import os
from pathlib import Path

from albums.app import Context
from albums.checks.check_types import FixResult
from albums.checks.numbering.check_disc_in_track_number import CheckDiscInTrackNumber
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField

from ...helpers import apply_automatic_fix


class TestCheckDiscInTrackNumber:
    def test_check_track_number_disc_in_tracknumber_ok(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-1.flac", tag={BasicField.TRACKNUMBER: "1", BasicField.DISCNUMBER: "1"}),
                Track(filename="1-2.flac", tag={BasicField.TRACKNUMBER: "2", BasicField.DISCNUMBER: "1"}),
                Track(filename="2-1.flac", tag={BasicField.TRACKNUMBER: "1", BasicField.DISCNUMBER: "2"}),
            ],
        )
        result = CheckDiscInTrackNumber(Context()).check(album)
        assert result is None

    def test_check_track_number_disc_in_tracknumber_unfixable(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-1.flac", tag={BasicField.TRACKNUMBER: "1-1", BasicField.DISCNUMBER: "1"}),
                Track(filename="1-2.flac", tag={BasicField.TRACKNUMBER: "1-2", BasicField.DISCNUMBER: "1"}),
                Track(filename="2-1.flac", tag={BasicField.TRACKNUMBER: "2-1", BasicField.DISCNUMBER: "2"}),
            ],
        )
        result = CheckDiscInTrackNumber(Context()).check(album)
        assert result is None

    def test_check_track_number_disc_in_tracknumber(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-1.flac", tag={BasicField.TRACKNUMBER: "1-1"}),
                Track(filename="1-2.flac", tag={BasicField.TRACKNUMBER: "1-2"}),
                Track(filename="2-1.flac", tag={BasicField.TRACKNUMBER: "2-1"}),
            ],
        )
        result = CheckDiscInTrackNumber(Context()).check(album)
        assert "track numbers formatted as number-dash-number, probably discnumber and tracknumber" in result.message
        fixer = result.fixer
        assert fixer
        assert fixer.options == [">> Split track number into disc number and track number"]
        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_set_basic_fields.call_count == 3
        assert mock_set_basic_fields.call_args.args == (
            Path(album.path) / album.tracks[2].filename,
            [(BasicField.DISCNUMBER, "2"), (BasicField.TRACKNUMBER, "1")],
        )
