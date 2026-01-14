import shutil
from mutagen.flac import FLAC
from albums.database import connection, selector
from albums.library.scanner import scan
from .create_library import create_album_in_library, create_library


class TestScanner:
    sample_library = [
        {
            "path": "bar/",
            "tracks": [
                {"source_file": "1.flac", "tags": {"title": "1"}},
                {"source_file": "2.flac", "tags": {"title": "2"}},
                {"source_file": "3.flac", "tags": {"title": "3"}},
            ],
        },
        {"path": "foo/", "tracks": [{"source_file": "1.mp3", "tags": {"title": "1"}}, {"source_file": "2.mp3", "tags": {"title": "2"}}]},
    ]

    def test_initial_scan(self):
        with connection.open(connection.MEMORY) as db:
            library = create_library("test_initial_scan", self.sample_library)
            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))

            assert len(result) == 2
            assert result[0]["path"] == "bar/"
            assert result[1]["path"] == "foo/"  # albums were scanned in lexical order

            # flac files
            assert len(result[0]["tracks"]) == 3
            assert result[0]["tracks"][0]["file_size"] > 1
            assert result[0]["tracks"][0]["modify_timestamp"] > 1
            assert result[0]["tracks"][0]["stream"]["sample_rate"] == 44100
            assert result[0]["tracks"][0]["stream"]["codec"] == "FLAC"
            assert result[0]["tracks"][0]["tags"]["title"] == "1"

            # mp3 files
            assert len(result[1]["tracks"]) == 2
            assert result[1]["tracks"][0]["file_size"] > 1
            assert result[1]["tracks"][0]["modify_timestamp"] > 1
            assert result[1]["tracks"][0]["stream"]["sample_rate"] == 44100
            assert result[1]["tracks"][0]["stream"]["codec"] == "MP3"
            assert result[1]["tracks"][0]["tags"]["title"] == "1"

    def test_scan_empty(self):
        with connection.open(connection.MEMORY) as db:
            library = create_library("test_scan_empty", [])
            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert result == []

    def test_scan_update(self):
        with connection.open(connection.MEMORY) as db:
            library = create_library("test_scan_update", self.sample_library)
            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))

            assert result[0]["tracks"][0]["source_file"] == "1.flac"
            assert result[0]["tracks"][0]["tags"]["title"] == "1"

            file = FLAC(library / result[0]["path"] / "1.flac")
            file["title"] = "new title"
            file.save()

            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert result[0]["tracks"][0]["tags"]["title"] == "new title"

    def test_scan_add(self):
        with connection.open(connection.MEMORY) as db:
            library = create_library("test_scan_add", [self.sample_library[1]])
            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 1
            assert result[0]["path"] == "foo/"

            create_album_in_library(library, self.sample_library[0])

            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 2
            assert result[0]["path"] == "bar/"

    def test_scan_remove(self):
        with connection.open(connection.MEMORY) as db:
            library = create_library("test_scan_remove", self.sample_library)
            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 2
            assert result[0]["path"] == "bar/"

            shutil.rmtree(library / "bar", ignore_errors=True)

            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 1
            assert result[0]["path"] == "foo/"
