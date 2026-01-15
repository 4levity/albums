from albums.checks.check_album_artist import CheckAlbumArtist
from albums.context import AppContext
from albums.types import Album, Track


class TestCheckAlbumArtist:
    def test_check_needs_albumartist_band__all(self):
        album = Album(
            "",
            [Track("1.flac", {"artist": ["A"]}), Track("2.flac", {"artist": ["B"]}), Track("3.flac", {"artist": ["B"]})],
        )
        result = CheckAlbumArtist(AppContext()).check(album)
        assert result.message == "multiple artists but no album artist (['A', 'B'] ...)"

    def test_check_needs_albumartist_band__one(self):
        # some tracks with albumartist
        album = Album(
            "",
            [
                Track("1", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2", {"artist": ["B"], "albumartist": ["Foo"]}),
                Track("3", {"artist": ["B"]}),
            ],
        )
        result = CheckAlbumArtist(AppContext()).check(album)
        assert result.message == "multiple artists but no album artist (['A', 'B'] ...)"

    def test_multiple_albumartist_band(self):
        album = Album(
            "",
            [
                Track("1", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2", {"artist": ["B"], "albumartist": ["Foo"]}),
                Track("3", {"artist": ["B"], "albumartist": ["Bar"]}),
            ],
        )
        result = CheckAlbumArtist(AppContext()).check(album)
        assert result.message == "multiple album artist values (['Foo', 'Bar'] ...)"

    def test_multiple_albumartist_band__same_artist(self):
        album = Album(
            "",
            [
                Track("1", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2", {"artist": ["A"], "albumartist": ["Bar"]}),
            ],
        )
        result = CheckAlbumArtist(AppContext()).check(album)
        assert result.message == "multiple album artist values (['Foo', 'Bar'] ...)"

    def test_multiple_albumartist_band__same_artist_2(self):
        album = Album(
            "",
            [
                Track("1", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2", {"artist": ["A"]}),
            ],
        )
        result = CheckAlbumArtist(AppContext()).check(album)
        assert result.message == "multiple album artist values (['Foo', ''] ...)"

    def test_albumartist_and_band(self):
        album = Album(
            "",
            [
                Track("1", {"artist": ["A"], "albumartist": ["Foo"], "Band": "Foo"}),
                Track("2", {"artist": ["B"], "albumartist": ["Foo"], "Band": "Foo"}),
            ],
        )
        result = CheckAlbumArtist(AppContext()).check(album)
        assert result.message == "albumartist and band tags both present"

    def test_albumartist__ok(self):
        album = Album(
            "",
            [
                Track("1", {"artist": ["A"], "albumartist": ["A"]}),
                Track("2", {"artist": ["B"], "albumartist": ["A"]}),
            ],
        )
        checker = CheckAlbumArtist(AppContext())
        result = checker.check(album)
        assert result is None

        # different artists, all albumartist the same
        album.tracks[1].tags["artist"] = ["A"]
        result = checker.check(album)
        assert result is None
