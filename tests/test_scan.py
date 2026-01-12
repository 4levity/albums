from pathlib import Path
from albums.database import connection, selector
from albums.library.scanner import scan


class TestScanner:
    test_data_path = Path(__file__).resolve().parent / "data"

    def test_scan(self):
        db = connection.open(":memory:")

        result = list(selector.select_albums(db, [], [], False))
        assert result == []

        scan(db, self.test_data_path / "albums_1")

        result = list(selector.select_albums(db, [], [], False))
        assert len(result) == 2
        assert result[0]["path"] == "bar/"
        assert result[1]["path"] == "foo/"  # should be scanned in lexical order
        assert len(result[0]["tracks"]) == 3
        assert len(result[1]["tracks"]) == 2
