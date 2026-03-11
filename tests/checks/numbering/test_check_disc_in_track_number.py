import os
from pathlib import Path

from albums.app import Context
from albums.checks.numbering.check_disc_in_track_number import CheckDiscInTrackNumber
from albums.tagger.folder import AlbumTagger
from albums.types import BasicTag
from albums.database.models import AlbumEntity, TrackEntity, TrackTagEntity


class TestCheckDiscInTrackNumber:
    def test_check_track_number_disc_in_tracknumber_ok(self, mocker):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1-1.flac",
                    tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")],
                ),
                TrackEntity(
                    filename="1-2.flac",
                    tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")],
                ),
                TrackEntity(
                    filename="2-1.flac",
                    tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2")],
                ),
            ],
        )
        result = CheckDiscInTrackNumber(Context()).check(album)
        assert result is None

    def test_check_track_number_disc_in_tracknumber_unfixable(self, mocker):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1-1.flac",
                    tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1-1"), TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")],
                ),
                TrackEntity(
                    filename="1-2.flac",
                    tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1-2"), TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")],
                ),
                TrackEntity(
                    filename="2-1.flac",
                    tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2-1"), TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2")],
                ),
            ],
        )
        result = CheckDiscInTrackNumber(Context()).check(album)
        assert result is None

    def test_check_track_number_disc_in_tracknumber(self, mocker):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(filename="1-1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1-1")]),
                TrackEntity(filename="1-2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1-2")]),
                TrackEntity(filename="2-1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2-1")]),
            ],
        )
        result = CheckDiscInTrackNumber(Context()).check(album)
        assert "track numbers formatted as number-dash-number, probably discnumber and tracknumber" in result.message
        fixer = result.fixer
        assert fixer
        assert fixer.options == [">> Split track number into disc number and track number"]
        assert fixer.option_automatic_index == 0
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        assert fixer.fix(fixer.options[fixer.option_automatic_index])
        assert mock_set_basic_tags.call_count == 3
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[2].filename,
            [(BasicTag.DISCNUMBER, "2"), (BasicTag.TRACKNUMBER, "1")],
        )
