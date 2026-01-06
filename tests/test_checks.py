from albums import checks


class TestChecks:
    def test_count_matching_prefixes(self):
        sorted_list = ["b", "d", "dd", "f"]
        assert checks.count_matching_prefixes(sorted_list, "d") == 2
        assert checks.count_matching_prefixes(sorted_list, "dd") == 1
        assert checks.count_matching_prefixes(sorted_list, "b") == 1
        assert checks.count_matching_prefixes(sorted_list, "f") == 1
        assert checks.count_matching_prefixes(sorted_list, "c") == 0

    def test_check_needs_albumartist_band__all(self):
        albums = {
            "": {
                "path": "",
                "tracks": [{"SourceFile": "1.flac", "Artist": "A"}, {"SourceFile": "2.flac", "Artist": "B"}, {"SourceFile": "3.flac", "Artist": "B"}],
            }
        }
        checks_enabled = {"needs_albumartist_band": "true"}
        result = checks.check(albums[""], checks_enabled, albums)
        assert result == [{"message": "multiple artists but no album artist (['A', 'B'] ...)"}]

    def test_check_needs_albumartist_band__one(self):
        # some tracks with albumartist
        albums = {
            "": {
                "path": "",
                "tracks": [
                    {"SourceFile": "1", "Artist": "A", "Albumartist": "Foo"},
                    {"SourceFile": "2", "Artist": "B", "Albumartist": "Foo"},
                    {"SourceFile": "3", "Artist": "B"},
                ],
            }
        }
        checks_enabled = {"needs_albumartist_band": "true"}
        result = checks.check(albums[""], checks_enabled, albums)
        assert result == [{"message": "multiple artists but no album artist (['A', 'B'] ...)"}]

    def test_multiple_albumartist_band(self):
        albums = {
            "": {
                "path": "",
                "tracks": [
                    {"SourceFile": "1", "Artist": "A", "Albumartist": "Foo"},
                    {"SourceFile": "2", "Artist": "B", "Albumartist": "Foo"},
                    {"SourceFile": "3", "Artist": "B", "Albumartist": "Bar"},
                ],
            }
        }
        checks_enabled = {"multiple_albumartist_band": "true"}
        result = checks.check(albums[""], checks_enabled, albums)
        assert result == [{"message": "multiple album artist values (['Foo', 'Bar'] ...)"}]

    def test_multiple_albumartist_band__same_artist(self):
        albums = {
            "": {
                "path": "",
                "tracks": [
                    {"SourceFile": "1", "Artist": "A", "Albumartist": "Foo"},
                    {"SourceFile": "2", "Artist": "A", "Albumartist": "Bar"},
                ],
            }
        }
        checks_enabled = {"multiple_albumartist_band": "true"}
        result = checks.check(albums[""], checks_enabled, albums)
        assert result == [{"message": "multiple album artist values (['Foo', 'Bar'] ...)"}]

    def test_multiple_albumartist_band__same_artist_2(self):
        albums = {
            "": {
                "path": "",
                "tracks": [
                    {"SourceFile": "1", "Artist": "A", "Albumartist": "Foo"},
                    {"SourceFile": "2", "Artist": "A"},
                ],
            }
        }
        checks_enabled = {"multiple_albumartist_band": "true"}
        result = checks.check(albums[""], checks_enabled, albums)
        assert result == [{"message": "multiple album artist values (['Foo', ''] ...)"}]

    def test_albumartist_and_band(self):
        albums = {
            "": {
                "path": "",
                "tracks": [
                    {"SourceFile": "1", "Artist": "A", "Albumartist": "Foo", "Band": "Foo"},
                    {"SourceFile": "2", "Artist": "B", "Albumartist": "Foo", "Band": "Foo"},
                ],
            }
        }
        checks_enabled = {"albumartist_and_band": "true"}
        result = checks.check(albums[""], checks_enabled, albums)
        assert result == [{"message": "albumartist and band tags both present"}]

    def test_albumartist__ok(self):
        albums = {
            "": {
                "path": "",
                "tracks": [
                    {"SourceFile": "1", "Artist": "A", "Albumartist": "A"},
                    {"SourceFile": "2", "Artist": "B", "Albumartist": "A"},
                ],
            }
        }
        checks_enabled = {"albumartist_and_band": "true", "multiple_albumartist_band": "true", "needs_albumartist_band": "true"}
        result = checks.check(albums[""], checks_enabled, albums)
        assert result == []

        # different artists, all albumartist the same
        albums[""]["tracks"][1]["Artist"] = "A"
        result = checks.check(albums[""], checks_enabled, albums)
        assert result == []

    def test_metadata_warning(self):
        album = {
            "path": "",
            "tracks": [
                {"SourceFile": "1.flac", "Artist": "Alice", "Warning": "WARNING 1"},
                {"SourceFile": "2.flac", "Artist": "Alice"},
            ],
        }
        albums_cache = {album["path"]: album}
        checks_enabled = {"metadata_warnings": "true"}
        result = checks.check(album, checks_enabled, albums_cache)
        assert result == [{"message": f"tagger warnings ({['WARNING 1']}"}]

        # same warning on two tracks
        album["tracks"][1]["Warning"] = "WARNING 1"
        result = checks.check(album, checks_enabled, albums_cache)
        assert result == [{"message": f"tagger warnings ({['WARNING 1']}"}]

        # two different warnings
        album["tracks"][1]["Warning"] = "WARNING 2"
        result = checks.check(album, checks_enabled, albums_cache)
        assert result == [{"message": f"tagger warnings ({['WARNING 1', 'WARNING 2']}"}]

    def test_required_tags(self):
        album = {
            "path": "",
            "tracks": [
                {"SourceFile": "1.flac", "Artist": "Alice"},
                {"SourceFile": "2.flac"},
            ],
        }
        albums_cache = {album["path"]: album}
        checks_enabled = {"required_tags": "Artist|Title"}
        result = checks.check(album, checks_enabled, albums_cache)
        assert result == [{"message": "tracks missing required tags ({'Title': 2, 'Artist': 1}"}]

        # one tag missing from both
        album["tracks"][1]["Artist"] = "Alice"
        result = checks.check(album, checks_enabled, albums_cache)
        assert result == [{"message": "tracks missing required tags ({'Title': 2}"}]

        # no tags missing
        album["tracks"][0]["Title"] = "one"
        album["tracks"][1]["Title"] = "two"
        result = checks.check(album, checks_enabled, albums_cache)
        assert result == []

    def test_album_under_album(self):
        albums_cache = {
            "foo/bar": {"path": "foo/bar", "tracks": [{"SourceFile": "1.flac"}]},
            "foo": {"path": "foo", "tracks": [{"SourceFile": "1.flac"}]},
        }
        checks_enabled = {"album_under_album": "true"}
        result = checks.check(albums_cache["foo"], checks_enabled, albums_cache)
        assert result == [{"message": "there are 1 albums in directories under album foo"}]
        result = checks.check(albums_cache["foo/bar"], checks_enabled, albums_cache)
        assert result == []
