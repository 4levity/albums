import contextlib
import os
import shutil

from mutagen.flac import FLAC

from albums.app import Context
from albums.database import connection, selector
from albums.library.scanner import scan
from albums.types import Album, Picture, PictureType, Track

from .fixtures.create_library import create_album_in_library, create_library


def context(db, library):
    context = Context()
    context.db = db
    context.library_root = library
    return context


class TestScanner:
    sample_library = [
        Album(
            "bar/",
            [
                Track("1.flac", {"title": ["1"]}),
                Track("2.flac", {"title": ["2"]}),
                Track("3.flac", {"title": ["3"]}),
            ],
            [],
            [],
            {"cover.png": Picture(PictureType.COVER_FRONT, "ignored", 0, 0, 0, b"")},
        ),
        Album("foo/", [Track("1.mp3", {"title": ["1"]}), Track("2.mp3", {"title": ["2"]})]),
        Album("baz/", [Track("1.wma", {"title": ["one"]}), Track("2.wma", {"title": ["two"]})]),
    ]

    def test_initial_scan(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_initial_scan", self.sample_library)
            scan(context(db, library))
            result = list(selector.select_albums(db, [], [], False))

            assert len(result) == 3
            assert result[0].path == "bar/"
            assert result[2].path == "foo/"  # albums were scanned in lexical order

            # flac files
            assert len(result[0].tracks) == 3
            assert result[0].tracks[0].file_size > 1
            assert result[0].tracks[0].modify_timestamp > 1
            assert result[0].tracks[0].stream.sample_rate == 44100
            assert result[0].tracks[0].stream.codec == "FLAC"
            assert result[0].tracks[0].tags["title"] == ["1"]

            # wma files
            assert len(result[1].tracks) == 2
            assert result[1].tracks[0].file_size > 1
            assert result[1].tracks[0].modify_timestamp > 1
            assert result[1].tracks[0].stream.sample_rate == 44100
            assert result[1].tracks[0].stream.codec == "Windows Media Audio V8"
            assert result[1].tracks[0].tags["title"] == ["one"]

            # mp3 files
            assert len(result[1].tracks) == 2
            assert result[2].tracks[0].file_size > 1
            assert result[2].tracks[0].modify_timestamp > 1
            assert result[2].tracks[0].stream.sample_rate == 44100
            assert result[2].tracks[0].stream.codec == "MP3"
            assert result[2].tracks[0].tags["title"] == ["1"]

            # image files in folder
            assert len(result[0].picture_files) == 1
            cover_png = result[0].picture_files.get("cover.png")
            assert cover_png
            assert cover_png.format == "image/png"
            assert cover_png.modify_timestamp
            assert cover_png.picture_type == PictureType.COVER_FRONT

    def test_scan_empty(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_scan_empty", [])
            scan(context(db, library))
            result = list(selector.select_albums(db, [], [], False))
            assert result == []

    def test_scan_no_tags(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library(
                "test_scan_no_tags",
                [Album("bar/", [Track("1.flac")]), Album("foo/", [Track("1.mp3")]), Album("baz/", [Track("1.wma")])],
            )
            scan(context(db, library))
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 3

    def test_scan_update(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_scan_update", self.sample_library)
            ctx = context(db, library)
            scan(ctx)
            result = list(selector.select_albums(db, [], [], False))

            assert result[0].tracks[0].filename == "1.flac"
            assert result[0].tracks[0].tags["title"] == ["1"]

            file = FLAC(library / result[0].path / "1.flac")
            file["title"] = "new title"
            file.save()

            scan(ctx)
            result = list(selector.select_albums(db, [], [], False))
            assert result[0].tracks[0].tags["title"] == ["new title"]

    def test_scan_add(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_scan_add", [self.sample_library[1]])
            ctx = context(db, library)
            scan(ctx)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 1
            assert result[0].path == "foo/"

            create_album_in_library(library, self.sample_library[0])

            scan(ctx)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 2
            assert result[0].path == "bar/"

    def test_scan_remove_album(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_scan_remove", self.sample_library)
            ctx = context(db, library)
            scan(ctx)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 3
            assert result[0].path == "bar/"

            # remove a folder that contains an album (removed without scanning)
            shutil.rmtree(library / "bar", ignore_errors=True)
            scan(ctx)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 2
            assert result[0].path == "baz/"

            # remove the tracks but the folder is still there (removed when scanned)
            shutil.rmtree(library / "baz", ignore_errors=True)
            os.mkdir(library / "baz")
            scan(ctx)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 1
            assert result[0].path == "foo/"

    def test_scan_remove_picture(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_scan_remove_picture", [self.sample_library[0]])
            ctx = context(db, library)
            scan(ctx)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result[0].picture_files) == 1

            (library / self.sample_library[0].path / "cover.png").unlink()

            scan(ctx)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result[0].picture_files) == 0

    def test_scan_filtered(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            library = create_library("test_scan_filtered", self.sample_library)
            ctx = context(db, library)
            scan(ctx)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 3

            delete_album = result[0].path
            shutil.rmtree(library / result[0].path, ignore_errors=True)
            scan(ctx, lambda: [(result[1].path, result[1].album_id)])

            # deleted path was not scanned, so album is still there
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 3
            assert result[0].path == delete_album
