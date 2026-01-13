from albums.database import connection, selector
from albums.library.scanner import scan
from .create_library import create_library


class TestScanner:
    def test_scan(self):
        db = connection.open(":memory:")

        result = list(selector.select_albums(db, [], [], False))
        assert result == []

        library = create_library(
            "albums_2",
            [
                {"path": "bar/", "tracks": [{"source_file": "1.flac"}, {"source_file": "2.flac"}, {"source_file": "3.flac"}]},
                {"path": "foo/", "tracks": [{"source_file": "1.flac"}, {"source_file": "2.flac"}]},
            ],
        )

        scan(db, library)

        result = list(selector.select_albums(db, [], [], False))
        assert len(result) == 2
        assert result[0]["path"] == "bar/"
        assert result[1]["path"] == "foo/"  # should be scanned in lexical order
        assert len(result[0]["tracks"]) == 3
        assert len(result[1]["tracks"]) == 2
