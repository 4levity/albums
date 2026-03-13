import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.tags.check_track_title import CheckTrackTitle
from albums.database.models import AlbumEntity, TrackEntity, TrackTagEntity
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import BasicTag


class TestCheckTrackTitle:
    def test_check_track_title_ok(self):
        album = AlbumEntity(
            path="Foobar" + os.sep,
            tracks=[
                TrackEntity(filename="1 foo.mp3", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="foo")]),
                TrackEntity(filename="2 bar.mp3", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="bar")]),
                TrackEntity(filename="3 baz.mp3", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="baz")]),
            ],
        )
        result = CheckTrackTitle(Context()).check(album)
        assert result is None

    def test_check_track_title_guess_all(self, mocker):
        album = AlbumEntity(
            path="Foobar" + os.sep,
            tracks=[
                TrackEntity(filename="1 foo.flac"),
                TrackEntity(filename="2 - bar.flac"),
                TrackEntity(filename="3. baz.flac"),
                TrackEntity(filename="bop.flac"),
            ],
        )
        result = CheckTrackTitle(Context()).check(album)
        assert result is not None
        assert "4 tracks missing title" in result.message
        assert result.fixer.options == [">> Use proposed track titles"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 4
        path = Path(album.path)
        assert mock_set_basic_tags.call_args_list == [
            call(path / album.tracks[0].filename, [(BasicTag.TITLE, "foo")]),
            call(path / album.tracks[1].filename, [(BasicTag.TITLE, "bar")]),
            call(path / album.tracks[2].filename, [(BasicTag.TITLE, "baz")]),
            call(path / album.tracks[3].filename, [(BasicTag.TITLE, "bop")]),
        ]

    def test_check_track_title_guess_some(self, mocker):
        album = AlbumEntity(
            path="Foobar" + os.sep,
            tracks=[
                TrackEntity(filename="1 foo.flac", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="foo")]),
                TrackEntity(filename="2 bar.flac"),
                TrackEntity(filename="3.flac"),
            ],
        )
        result = CheckTrackTitle(Context()).check(album)
        assert result is not None
        assert "2 tracks missing title" in result.message
        assert result.fixer.options == [">> Use proposed track titles"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1  # track 3 could not be fixed
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[1].filename, [(BasicTag.TITLE, "bar")])

    def test_check_track_title_no_guess(self, mocker):
        album = AlbumEntity(path="Foobar" + os.sep, tracks=[TrackEntity(filename="1.flac"), TrackEntity(filename="2.flac")])
        result = CheckTrackTitle(Context()).check(album)
        assert result is not None
        assert "2 tracks missing title" in result.message
        assert not result.fixer

    def test_check_track_title_with_disc_number(self, mocker):
        album = AlbumEntity(
            path="Foobar" + os.sep,
            tracks=[
                TrackEntity(filename="1 foo.flac", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="foo")]),
                TrackEntity(filename="2 bar.flac"),
                TrackEntity(filename="3 baz.flac", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="baz")]),
            ],
        )
        result = CheckTrackTitle(Context()).check(album)
        assert result is not None
        assert "1 tracks missing title" in result.message
        assert result.fixer.options == [">> Use proposed track titles"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[1].filename, [(BasicTag.TITLE, "bar")])
