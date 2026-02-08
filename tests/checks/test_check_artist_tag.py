from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.check_artist_tag import CheckArtistTag
from albums.types import Album, Track


class TestCheckArtistTag:
    def test_artist_tag_ok(self):
        album = Album(
            "A/",
            [Track("1.flac", {"artist": ["A"]}), Track("2.flac", {"artist": ["B"]})],
        )
        result = CheckArtistTag(Context()).check(album)
        assert result is None

    def test_artist_tag_automatic(self, mocker):
        album = Album("Foo/Bar/", [Track("1.flac"), Track("2.flac")])
        result = CheckArtistTag(Context()).check(album)
        assert result
        assert "2 tracks missing artist tag" in result.message
        assert result.fixer
        assert result.fixer.options == ["Foo"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch("albums.checks.check_artist_tag.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        path = Path(album.path)
        assert mock_set_basic_tags.call_args_list == [
            call(path / album.tracks[0].filename, [("artist", "Foo")]),
            call(path / album.tracks[1].filename, [("artist", "Foo")]),
        ]

    def test_artist_tag_conflict(self, mocker):
        album = Album("Foo/Bar/", [Track("1.flac", {"artist": ["Baz"]}), Track("2.flac", {"artist": ["Baz"]}), Track("3.flac")])
        result = CheckArtistTag(Context()).check(album)
        assert result
        assert "1 tracks missing artist tag" in result.message
        assert result.fixer
        assert result.fixer.options == ["Baz", "Foo"]
        assert result.fixer.option_automatic_index is None
