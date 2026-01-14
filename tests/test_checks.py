from albums.library import checks
from albums.database import connection, operations


class TestChecks:
    def test_check_needs_albumartist_band__all(self):
        album = {
            "path": "",
            "tracks": [
                {"source_file": "1.flac", "tags": {"artist": "A"}},
                {"source_file": "2.flac", "tags": {"artist": "B"}},
                {"source_file": "3.flac", "tags": {"artist": "B"}},
            ],
        }
        checks_enabled = {"needs_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "multiple artists but no album artist (['A', 'B'] ...)"}]

    def test_check_needs_albumartist_band__one(self):
        # some tracks with albumartist
        album = {
            "path": "",
            "tracks": [
                {"source_file": "1", "tags": {"artist": "A", "albumartist": "Foo"}},
                {"source_file": "2", "tags": {"artist": "B", "albumartist": "Foo"}},
                {"source_file": "3", "tags": {"artist": "B"}},
            ],
        }
        checks_enabled = {"needs_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "multiple artists but no album artist (['A', 'B'] ...)"}]

    def test_multiple_albumartist_band(self):
        album = {
            "path": "",
            "tracks": [
                {"source_file": "1", "tags": {"artist": "A", "albumartist": "Foo"}},
                {"source_file": "2", "tags": {"artist": "B", "albumartist": "Foo"}},
                {"source_file": "3", "tags": {"artist": "B", "albumartist": "Bar"}},
            ],
        }
        checks_enabled = {"multiple_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "multiple album artist values (['Foo', 'Bar'] ...)"}]

    def test_multiple_albumartist_band__same_artist(self):
        album = {
            "path": "",
            "tracks": [
                {"source_file": "1", "tags": {"artist": "A", "albumartist": "Foo"}},
                {"source_file": "2", "tags": {"artist": "A", "albumartist": "Bar"}},
            ],
        }
        checks_enabled = {"multiple_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "multiple album artist values (['Foo', 'Bar'] ...)"}]

    def test_multiple_albumartist_band__same_artist_2(self):
        album = {
            "path": "",
            "tracks": [
                {"source_file": "1", "tags": {"artist": "A", "albumartist": "Foo"}},
                {"source_file": "2", "tags": {"artist": "A"}},
            ],
        }
        checks_enabled = {"multiple_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "multiple album artist values (['Foo', ''] ...)"}]

    def test_albumartist_and_band(self):
        album = {
            "path": "",
            "tracks": [
                {"source_file": "1", "tags": {"artist": "A", "albumartist": "Foo", "Band": "Foo"}},
                {"source_file": "2", "tags": {"artist": "B", "albumartist": "Foo", "Band": "Foo"}},
            ],
        }
        checks_enabled = {"albumartist_and_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "albumartist and band tags both present"}]

    def test_albumartist__ok(self):
        album = {
            "path": "",
            "tracks": [
                {"source_file": "1", "tags": {"artist": "A", "albumartist": "A"}},
                {"source_file": "2", "tags": {"artist": "B", "albumartist": "A"}},
            ],
        }
        checks_enabled = {"albumartist_and_band": "true", "multiple_albumartist_band": "true", "needs_albumartist_band": "true"}
        result = checks.check(None, album, checks_enabled)
        assert result == []

        # different artists, all albumartist the same
        album["tracks"][1]["artist"] = "A"
        result = checks.check(None, album, checks_enabled)
        assert result == []

    def test_required_tags(self):
        album = {
            "path": "",
            "tracks": [
                {"source_file": "1.flac", "tags": {"artist": "Alice"}},
                {"source_file": "2.flac", "tags": {}},
            ],
        }
        checks_enabled = {"required_tags": "artist|Title"}
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "tracks missing required tags {'Title': 2, 'artist': 1}"}]

        # one tag missing from both
        album["tracks"][1]["tags"]["artist"] = "Alice"
        result = checks.check(None, album, checks_enabled)
        assert result == [{"message": "tracks missing required tags {'Title': 2}"}]

        # no tags missing
        album["tracks"][0]["tags"]["Title"] = "one"
        album["tracks"][1]["tags"]["Title"] = "two"
        result = checks.check(None, album, checks_enabled)
        assert result == []

    def test_album_under_album(self):
        track_template = {"file_size": 1, "modify_timestamp": 0, "stream": {"length": 1.5}, "tags": {}}
        albums = [
            {"path": "foo/bar", "tracks": [track_template | {"source_file": "1.flac"}]},
            {"path": "foo", "tracks": [track_template | {"source_file": "1.flac"}]},
        ]
        db = connection.open(":memory:")
        operations.add(db, albums[0])
        operations.add(db, albums[1])
        checks_enabled = {"album_under_album": "true"}
        result = checks.check(db, albums[1], checks_enabled)
        assert result == [{"message": "there are 1 albums in directories under album foo"}]
        result = checks.check(db, albums[0], checks_enabled)
        assert result == []
