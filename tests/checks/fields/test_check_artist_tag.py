import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.fields.check_artist_tag import CheckArtistTag
from albums.entities import Album, Track
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import BasicField


class TestCheckArtistTag:
    def test_artist_tag_ok(self):
        album = Album(
            path="A" + os.sep,
            tracks=[
                Track(filename="1.flac", tag={BasicField.ARTIST: "A"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "B"}),
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

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        path = Path(album.path)
        assert mock_set_basic_fields.call_args_list == [
            call(path / album.tracks[0].filename, [(BasicField.ARTIST, "Foo")]),
            call(path / album.tracks[1].filename, [(BasicField.ARTIST, "Foo")]),
        ]

    def test_artist_tag_conflict(self, mocker):
        album = Album(
            path=f"Foo{os.sep}Bar{os.sep}",
            tracks=[
                Track(filename="1.flac", tag={BasicField.ARTIST: "Baz"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Baz"}),
                Track(filename="3.flac"),
            ],
        )
        result = CheckArtistTag(Context()).check(album)
        assert result
        assert "1 track missing artist tag" in result.message
        assert result.fixer
        assert result.fixer.options == ["Baz", "Foo"]
        assert result.fixer.option_automatic_index is None
