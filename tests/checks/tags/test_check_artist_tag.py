import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.tags.check_artist_tag import CheckArtistTag
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import BasicTag
from albums.types import Album, Tag, Track


class TestCheckArtistTag:
    def test_artist_tag_ok(self):
        album = Album(
            path="A" + os.sep,
            tracks=[
                Track(filename="1.flac", tags=[Tag(tag=BasicTag.ARTIST, value="A")]),
                Track(filename="2.flac", tags=[Tag(tag=BasicTag.ARTIST, value="B")]),
            ],
        )
        result = CheckArtistTag(Context()).check(album)
        assert result is None

    def test_artist_tag_automatic(self, mocker):
        album = Album(path=f"Foo{os.sep}Bar{os.sep}", tracks=[Track(filename="1.flac"), Track(filename="2.flac")])
        result = CheckArtistTag(Context()).check(album)
        assert result
        assert "2 tracks missing artist tag" in result.message
        assert result.fixer
        assert result.fixer.options == ["Foo"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        path = Path(album.path)
        assert mock_set_basic_tags.call_args_list == [
            call(path / album.tracks[0].filename, [(BasicTag.ARTIST, "Foo")]),
            call(path / album.tracks[1].filename, [(BasicTag.ARTIST, "Foo")]),
        ]

    def test_artist_tag_conflict(self, mocker):
        album = Album(
            path=f"Foo{os.sep}Bar{os.sep}",
            tracks=[
                Track(filename="1.flac", tags=[Tag(tag=BasicTag.ARTIST, value="Baz")]),
                Track(filename="2.flac", tags=[Tag(tag=BasicTag.ARTIST, value="Baz")]),
                Track(filename="3.flac"),
            ],
        )
        result = CheckArtistTag(Context()).check(album)
        assert result
        assert "1 tracks missing artist tag" in result.message
        assert result.fixer
        assert result.fixer.options == ["Baz", "Foo"]
        assert result.fixer.option_automatic_index is None
