import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.check_types import FixResult
from albums.checks.fields.check_artist import CheckArtistField
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField

from ...helpers import apply_automatic_fix


class TestCheckArtistField:
    def test_artist_field_ok(self):
        album = Album(
            path="A" + os.sep,
            tracks=[
                Track(filename="1.flac", tag={BasicField.ARTIST: "A"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "B"}),
            ],
        )
        result = CheckArtistField(Context()).check(album)
        assert result is None

    def test_artist_field_automatic(self, mocker):
        album = Album(path=f"Foo{os.sep}Bar{os.sep}", tracks=[Track(filename="1.flac"), Track(filename="2.flac")])
        result = CheckArtistField(Context()).check(album)
        assert result
        assert "2 tracks missing artist field" in result.message
        assert result.fixer
        assert result.fixer.options == ["Foo"]

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        path = Path(album.path)
        assert mock_set_basic_fields.call_args_list == [
            call(path / album.tracks[0].filename, [(BasicField.ARTIST, "Foo")]),
            call(path / album.tracks[1].filename, [(BasicField.ARTIST, "Foo")]),
        ]

    def test_artist_field_conflict(self, mocker):
        album = Album(
            path=f"Foo{os.sep}Bar{os.sep}",
            tracks=[
                Track(filename="1.flac", tag={BasicField.ARTIST: "Baz"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Baz"}),
                Track(filename="3.flac"),
            ],
        )
        result = CheckArtistField(Context()).check(album)
        assert result
        assert "1 track missing artist field" in result.message
        assert result.fixer
        assert result.fixer.options == ["Baz", "Foo"]
        assert result.fixer.option_automatic_index is None

    def test_ignore_parent_folders_case_insensitive(self):
        # configured ignore_parent_folders values match case-insensitively, so a mixed-case value
        # keeps the parent folder out of the proposed artist values
        ctx = Context()
        ctx.config.checks = {CheckArtistField.name: {"enabled": True, "ignore_parent_folders": ["Compilations"]}}
        album = Album(
            path=f"compilations{os.sep}Foo{os.sep}",
            tracks=[Track(filename="1.flac"), Track(filename="2.flac")],
        )
        result = CheckArtistField(ctx).check(album)
        assert result
        assert "2 tracks missing artist field" in result.message
        assert result.fixer
        assert result.fixer.options == []
