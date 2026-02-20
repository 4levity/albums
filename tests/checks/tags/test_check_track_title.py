import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.tags.check_track_title import CheckTrackTitle
from albums.types import Album, Track


class TestCheckTrackTitle:
    def test_check_track_title_ok(self):
        album = Album(
            "Foobar" + os.sep,
            [
                Track("1 foo.mp3", {"title": ["foo"]}),
                Track("2 bar.mp3", {"title": ["bar"]}),
                Track("3 baz.mp3", {"title": ["baz"]}),
            ],
        )
        result = CheckTrackTitle(Context()).check(album)
        assert result is None

    def test_check_track_title_guess_all(self, mocker):
        album = Album("Foobar" + os.sep, [Track("1 foo.flac"), Track("2 - bar.flac"), Track("3. baz.flac"), Track("bop.flac")])
        result = CheckTrackTitle(Context()).check(album)
        assert result is not None
        assert "4 tracks missing title" in result.message
        assert result.fixer.options == [">> Use proposed track titles"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch("albums.checks.tags.check_track_title.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 4
        path = Path(album.path)
        assert mock_set_basic_tags.call_args_list == [
            call(path / album.tracks[0].filename, [("title", "foo")]),
            call(path / album.tracks[1].filename, [("title", "bar")]),
            call(path / album.tracks[2].filename, [("title", "baz")]),
            call(path / album.tracks[3].filename, [("title", "bop")]),
        ]

    def test_check_track_title_guess_some(self, mocker):
        album = Album(
            "Foobar" + os.sep,
            [
                Track("1 foo.flac", {"title": ["foo"]}),
                Track("2 bar.flac"),
                Track("3.flac"),
            ],
        )
        result = CheckTrackTitle(Context()).check(album)
        assert result is not None
        assert "2 tracks missing title" in result.message
        assert result.fixer.options == [">> Use proposed track titles"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch("albums.checks.tags.check_track_title.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1  # track 3 could not be fixed
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[1].filename, [("title", "bar")])

    def test_check_track_title_no_guess(self, mocker):
        album = Album("Foobar" + os.sep, [Track("1.flac"), Track("2.flac")])
        result = CheckTrackTitle(Context()).check(album)
        assert result is not None
        assert "2 tracks missing title" in result.message
        assert not result.fixer

    def test_check_track_title_with_disc_number(self, mocker):
        album = Album("Foobar" + os.sep, [Track("1 foo.flac", {"title": ["foo"]}), Track("2 bar.flac"), Track("3 baz.flac", {"title": ["baz"]})])
        result = CheckTrackTitle(Context()).check(album)
        assert result is not None
        assert "1 tracks missing title" in result.message
        assert result.fixer.options == [">> Use proposed track titles"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch("albums.checks.tags.check_track_title.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[1].filename, [("title", "bar")])
