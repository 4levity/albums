from albums.app import Context
from albums.checks.tags.check_genre_present import CheckGenrePresent
from albums.tagger.types import BasicTag
from albums.types import Album, Track


class TestCheckGenrePresent:
    def test_genre_ok(self):
        tracks = [Track(filename="1.flac", tag={BasicTag.GENRE: "Rock"}), Track(filename="2.flac", tag={BasicTag.GENRE: "Rock"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckGenrePresent(Context()).check(album)
        assert result is None

    def test_genre_ok_none(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckGenrePresent(Context()).check(album)
        assert result is None

    def test_genre_missing(self):
        tracks = [Track(filename="1.flac", tag={BasicTag.GENRE: "Rock"}), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckGenrePresent(Context()).check(album)
        assert result is not None
        assert "genre policy=CONSISTENT but it is on some tracks and not others" in result.message

    def test_genre_inconsistent(self):
        tracks = [Track(filename="1.flac", tag={BasicTag.GENRE: "Rock"}), Track(filename="2.flac", tag={BasicTag.GENRE: "Country"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckGenrePresent(Context()).check(album)
        assert result is not None
        assert "genre per_track is false, but tracks have different genres, example Country and Rock" in result.message

    def test_genre_none_policy_always(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        ctx = Context()
        ctx.config.checks[CheckGenrePresent.name]["presence"] = "always"
        result = CheckGenrePresent(ctx).check(album)
        assert result is not None
        assert "genre policy=ALWAYS but it is not on all tracks" in result.message
