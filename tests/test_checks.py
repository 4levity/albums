import contextlib
from albums.library import checks
from albums.database import connection, operations
from albums.types import Album, Stream, Track


class TestChecks:
    def test_check_needs_albumartist_band__all(self):
        album = Album(
            "",
            [Track("1.flac", {"artist": "A"}), Track("2.flac", {"artist": "B"}), Track("3.flac", {"artist": "B"})],
        )
        checks_enabled = {"needs_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "multiple artists but no album artist (['A', 'B'] ...)"}]

    def test_check_needs_albumartist_band__one(self):
        # some tracks with albumartist
        album = Album(
            "",
            [Track("1", {"artist": "A", "albumartist": "Foo"}), Track("2", {"artist": "B", "albumartist": "Foo"}), Track("3", {"artist": "B"})],
        )
        checks_enabled = {"needs_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "multiple artists but no album artist (['A', 'B'] ...)"}]

    def test_multiple_albumartist_band(self):
        album = Album(
            "",
            [
                Track("1", {"artist": "A", "albumartist": "Foo"}),
                Track("2", {"artist": "B", "albumartist": "Foo"}),
                Track("3", {"artist": "B", "albumartist": "Bar"}),
            ],
        )
        checks_enabled = {"multiple_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "multiple album artist values (['Foo', 'Bar'] ...)"}]

    def test_multiple_albumartist_band__same_artist(self):
        album = Album(
            "",
            [
                Track("1", {"artist": "A", "albumartist": "Foo"}),
                Track("2", {"artist": "A", "albumartist": "Bar"}),
            ],
        )
        checks_enabled = {"multiple_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "multiple album artist values (['Foo', 'Bar'] ...)"}]

    def test_multiple_albumartist_band__same_artist_2(self):
        album = Album(
            "",
            [
                Track("1", {"artist": "A", "albumartist": "Foo"}),
                Track("2", {"artist": "A"}),
            ],
        )
        checks_enabled = {"multiple_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "multiple album artist values (['Foo', ''] ...)"}]

    def test_albumartist_and_band(self):
        album = Album(
            "",
            [
                Track("1", {"artist": "A", "albumartist": "Foo", "Band": "Foo"}),
                Track("2", {"artist": "B", "albumartist": "Foo", "Band": "Foo"}),
            ],
        )
        checks_enabled = {"albumartist_and_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "albumartist and band tags both present"}]

    def test_albumartist__ok(self):
        album = Album(
            "",
            [
                Track("1", {"artist": "A", "albumartist": "A"}),
                Track("2", {"artist": "B", "albumartist": "A"}),
            ],
        )
        checks_enabled = {"albumartist_and_band": "true", "multiple_albumartist_band": "true", "needs_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == []

        # different artists, all albumartist the same
        album.tracks[1].tags["artist"] = "A"
        result = checks.check(None, album, checks_enabled)
        assert result == []

    def test_required_tags(self):
        album = Album(
            "",
            [
                Track("1.flac", {"artist": "Alice"}),
                Track("2.flac", {}),
            ],
        )
        checks_enabled = {"required_tags": "artist|Title"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "tracks missing required tags {'Title': 2, 'artist': 1}"}]

        # one tag missing from both
        album.tracks[1].tags["artist"] = "Alice"
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "tracks missing required tags {'Title': 2}"}]

        # no tags missing
        album.tracks[0].tags["Title"] = "one"
        album.tracks[1].tags["Title"] = "two"
        result = checks.check(None, album, checks_enabled)
        assert result == []

    def test_album_under_album(self):
        def track(filename):
            return Track(filename, {}, 1, 0, Stream(1.5))

        albums = [
            Album("foo/bar/", [track("1.flac")]),
            Album("foo/", [track("1.flac")]),
            Album("foobar/", [track("1.flac")]),
        ]

        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            operations.add(db, albums[0])
            operations.add(db, albums[1])
            operations.add(db, albums[2])
            checks_enabled = {"album_under_album": "true"}
            result = checks.check(db, albums[1], checks_enabled)
            assert result == [{"message": "there are 1 albums in directories under album foo/"}]
            result = checks.check(db, albums[0], checks_enabled)
            assert result == []
