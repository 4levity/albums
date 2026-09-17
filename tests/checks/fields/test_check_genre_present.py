import os

import pytest

from albums.app import Context
from albums.checks.check_types import FixResult
from albums.checks.fields.check_genre_present import CheckGenrePresent
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField

from ...fixtures.create_library import create_library


class TestCheckGenrePresent:
    def test_genre_ok(self):
        tracks = [Track(filename="1.flac", tag={BasicField.GENRE: "Rock"}), Track(filename="2.flac", tag={BasicField.GENRE: "Rock"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckGenrePresent(Context()).check(album)
        assert result is None

    def test_genre_ok_none(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckGenrePresent(Context()).check(album)
        assert result is None

    def test_genre_missing(self):
        tracks = [Track(filename="1.flac", tag={BasicField.GENRE: "Rock"}), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckGenrePresent(Context()).check(album)
        assert result is not None
        assert "genre policy=CONSISTENT but it is on some tracks and not others" in result.message

    def test_genre_inconsistent(self):
        tracks = [Track(filename="1.flac", tag={BasicField.GENRE: "Rock"}), Track(filename="2.flac", tag={BasicField.GENRE: "Country"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckGenrePresent(Context()).check(album)
        assert result is not None
        assert "tracks have inconsistent genres (per_track=False), e.g. Country and Rock" in result.message

    def test_genre_none_policy_always(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        ctx = Context()
        ctx.config.checks[CheckGenrePresent.name]["presence"] = "always"
        result = CheckGenrePresent(ctx).check(album)
        assert result is not None
        assert "genre policy=ALWAYS but it is not on all tracks" in result.message

    def test_select_genres_must_be_list_of_strings(self):
        ctx = Context()
        ctx.config.checks[CheckGenrePresent.name]["select_genres"] = "Rock"
        with pytest.raises(ValueError, match="select_genres"):
            CheckGenrePresent(ctx)
        ctx.config.checks[CheckGenrePresent.name]["select_genres"] = ["Rock", 3]  # pyright: ignore[reportArgumentType]
        with pytest.raises(ValueError):
            CheckGenrePresent(ctx)

    def test_unsupported_file_type_skipped(self):
        tracks = [Track(filename="1.xyz", tag={BasicField.GENRE: "Rock"})]
        album = Album(path="foo", tracks=tracks)
        assert CheckGenrePresent(Context()).check(album) is None


class TestFixSetGenre:
    def test_fix_set_genre(self):
        tracks = [
            Track(filename="1.flac", tag={BasicField.GENRE: "Jazz"}),
            Track(filename="2.flac", tag={BasicField.GENRE: "Rock"}),
        ]
        album = Album(path="foo" + os.sep, tracks=tracks)
        library = create_library("genre_fix", [album])
        ctx = Context()
        ctx.config.library = library
        result = CheckGenrePresent(ctx).check(album)
        assert result is not None and result.fixer
        assert result.fixer.fix("Jazz") == FixResult.CHANGED_ALBUM
        tagger = AlbumTagger(library / album.path)
        for filename in ("1.flac", "2.flac"):
            with tagger.open(filename) as tag:
                assert dict(tag.get_fields())[BasicField.GENRE] == ("Jazz",)
