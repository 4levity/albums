import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.numbering.check_track_numbering import CheckTrackNumbering
from albums.database.models import AlbumEntity, TrackEntity, TrackTagEntity
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import BasicTag


class TestCheckTrackNumbering:
    def test_check_track_numbering_ok(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1")]),
                TrackEntity(filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2")]),
                TrackEntity(filename="3.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="3")]),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert result is None

    def test_check_track_number_total_ok(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="3")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="3")]
                ),
                TrackEntity(
                    filename="3.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="3"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="3")]
                ),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert result is None

    def test_check_tracktotal_policy(self):
        # just make sure config works, policy helper has its own tests for fixer
        album_with_all = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="2")]
                ),
            ],
        )
        album_with_none = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1")]),
                TrackEntity(filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2")]),
            ],
        )
        ctx = Context()
        ctx.config.checks = {CheckTrackNumbering.name: {"tracktotal_policy": "consistent"}}  # default
        check = CheckTrackNumbering(ctx)
        result = check.check(album_with_all)
        assert result is None
        result = check.check(album_with_none)
        assert result is None

        ctx.config.checks = {CheckTrackNumbering.name: {"tracktotal_policy": "always"}}
        check = CheckTrackNumbering(ctx)
        assert check.check(album_with_all) is None
        result = check.check(album_with_none)
        assert result
        assert "tracktotal policy=ALWAYS but it is not on all tracks" in result.message

        ctx.config.checks = {CheckTrackNumbering.name: {"tracktotal_policy": "never"}}
        check = CheckTrackNumbering(ctx)
        assert check.check(album_with_none) is None
        result = check.check(album_with_all)
        assert result
        assert "tracktotal policy=NEVER but it appears on tracks" in result.message

    def test_check_track_total_inconsistent(self, mocker):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="3.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="3"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="3")]
                ),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "some tracks have different track total values" in result.message
        fixer = result.fixer
        assert fixer
        assert fixer.options == [">> Set tracktotal to number of tracks: 3"]
        assert fixer.option_automatic_index == 0
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        assert fixer.fix(fixer.options[fixer.option_automatic_index])
        path = Path(album.path)
        assert mock_set_basic_tags.call_args_list == [
            call(path / album.tracks[0].filename, [(BasicTag.TRACKTOTAL, "3")]),
            call(path / album.tracks[1].filename, [(BasicTag.TRACKTOTAL, "3")]),
        ]

    def test_check_track_number_missing(self, mocker):
        album = AlbumEntity(
            path="foo" + os.sep, tracks=[TrackEntity(filename="1.flac"), TrackEntity(filename="2.flac"), TrackEntity(filename="3.flac")]
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "missing track numbers {1, 2, 3}" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Automatically renumber 3 tracks based on filenames"]
        assert result.fixer.option_automatic_index == 0
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        path = Path(album.path)
        assert mock_set_basic_tags.call_args_list == [
            call(path / album.tracks[0].filename, [(BasicTag.TRACKNUMBER, "1")]),
            call(path / album.tracks[1].filename, [(BasicTag.TRACKNUMBER, "2")]),
            call(path / album.tracks[2].filename, [(BasicTag.TRACKNUMBER, "3")]),
        ]

    def test_check_track_number_missing_on_one_disc(self, mocker):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(filename="1-1.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")]),
                TrackEntity(filename="1-2.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")]),
                TrackEntity(
                    filename="2-1.flac",
                    tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2")],
                ),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "missing track numbers on disc 1 {1, 2}" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Automatically renumber 2 tracks based on filenames"]
        assert result.fixer.option_automatic_index == 0
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        path = Path(album.path)
        assert mock_set_basic_tags.call_args_list == [
            call(path / album.tracks[0].filename, [(BasicTag.TRACKNUMBER, "1")]),
            call(path / album.tracks[1].filename, [(BasicTag.TRACKNUMBER, "2")]),
        ]

    def test_check_unexpected_track_number(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="3.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="3"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="2")]
                ),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "unexpected track numbers {3}" in result.message
        assert result.fixer is None

    def test_check_duplicate_track_number(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(filename="1 foo.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1")]),
                TrackEntity(filename="2 bar.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2")]),
                TrackEntity(filename="2 baz.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2")]),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "duplicate track numbers [2]" in result.message
        assert result.fixer is None

    def test_check_missing_track_with_totals(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="4")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="4")]
                ),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "tracks missing from album {3, 4}" in result.message
        assert result.fixer is None

    def test_check_missing_track_in_set(self):
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
                TrackEntity(
                    filename="2-4.flac",
                    tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="4"), TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2")],
                ),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "tracks missing from album on disc 2 {2, 3}" in result.message
        assert result.fixer is None

    def test_check_missing_track_without_totals(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1")]),
                TrackEntity(filename="4.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="4")]),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "tracks missing from album {2, 3}" in result.message
        assert result.fixer is None
