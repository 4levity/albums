import contextlib
import shutil
from mutagen.flac import FLAC
from albums.database import connection, selector
from albums.library.scanner import scan, DEFAULT_SUPPORTED_FILE_TYPES
from albums.types import Album, Track
from .create_library import create_album_in_library, create_library


class TestScanner:
    sample_library = [
        Album(
            "bar/",
            [
                Track("1.flac", {"title": "1"}),
                Track("2.flac", {"title": "2"}),
                Track("3.flac", {"title": "3"}),
            ],
        ),
        Album("foo/", [Track("1.mp3", {"title": "1"}), Track("2.mp3", {"title": "2"})]),
    ]

    def test_initial_scan(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_initial_scan", self.sample_library)
            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))

            assert len(result) == 2
            assert result[0].path == "bar/"
            assert result[1].path == "foo/"  # albums were scanned in lexical order

            # flac files
            assert len(result[0].tracks) == 3
            assert result[0].tracks[0].file_size > 1
            assert result[0].tracks[0].modify_timestamp > 1
            assert result[0].tracks[0].stream.sample_rate == 44100
            assert result[0].tracks[0].stream.codec == "FLAC"
            assert result[0].tracks[0].tags["title"] == ["1"]

            # mp3 files
            assert len(result[1].tracks) == 2
            assert result[1].tracks[0].file_size > 1
            assert result[1].tracks[0].modify_timestamp > 1
            assert result[1].tracks[0].stream.sample_rate == 44100
            assert result[1].tracks[0].stream.codec == "MP3"
            assert result[1].tracks[0].tags["title"] == ["1"]

    def test_scan_empty(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_scan_empty", [])
            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert result == []

    def test_scan_update(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_scan_update", self.sample_library)
            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))

            assert result[0].tracks[0].filename == "1.flac"
            assert result[0].tracks[0].tags["title"] == ["1"]

            file = FLAC(library / result[0].path / "1.flac")
            file["title"] = "new title"
            file.save()

            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert result[0].tracks[0].tags["title"] == ["new title"]

    def test_scan_add(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_scan_add", [self.sample_library[1]])
            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 1
            assert result[0].path == "foo/"

            create_album_in_library(library, self.sample_library[0])

            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 2
            assert result[0].path == "bar/"

    def test_scan_remove(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_scan_remove", self.sample_library)
            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 2
            assert result[0].path == "bar/"

            shutil.rmtree(library / "bar", ignore_errors=True)

            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 1
            assert result[0].path == "foo/"

    def test_scan_filtered(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_scan_filtered", self.sample_library)
            scan(db, library)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 2

            delete_album = result[0].path
            shutil.rmtree(library / result[0].path, ignore_errors=True)
            scan(db, library, DEFAULT_SUPPORTED_FILE_TYPES, lambda: [(result[1].path, result[1].album_id)])

            # deleted path was not scanned, so album is still there
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 2
            assert result[0].path == delete_album
