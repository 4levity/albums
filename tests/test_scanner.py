import os
import shutil

from mutagen.flac import FLAC
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from albums.app import SCANNER_VERSION, Context
from albums.database import connection
from albums.library.scanner import AlbumEntity, scan
from albums.picture.info import PictureInfo
from albums.types import Album, BasicTag, Path, PictureFile, Track

from .fixtures.create_library import create_album_in_library, create_library


def context(db: Engine, library: Path):
    context = Context()
    context.db = db
    context.config.library = library
    return context


class TestScanner:
    sample_library = [
        Album(
            "bar" + os.sep,
            [
                Track("1.flac", {BasicTag.TITLE: ["1"]}),
                Track("2.flac", {BasicTag.TITLE: ["2"]}),
                Track("3.flac", {BasicTag.TITLE: ["3"]}),
            ],
            [],
            [],
            [PictureFile("cover.jpg", PictureInfo("image/png", 410, 410, 24, 0, b""), 0, False)],
        ),
        Album("foo" + os.sep, [Track("1.mp3", {BasicTag.TITLE: ["1"]}), Track("2.mp3", {BasicTag.TITLE: ["2"]})]),
        Album("baz" + os.sep, [Track("1.wma", {BasicTag.TITLE: ["one"]}), Track("2.wma", {BasicTag.TITLE: ["two"]})]),
        Album("eee" + os.sep, [Track("1.m4a", {BasicTag.TITLE: ["one"]}), Track("2.m4a", {BasicTag.TITLE: ["two"]})]),
        Album("mob" + os.sep, [Track("1.aiff", {BasicTag.TITLE: ["one"]}), Track("2.aiff", {BasicTag.TITLE: ["two"]})]),
    ]

    def test_initial_scan(self):
        db = connection.open(connection.MEMORY)
        try:
            library = create_library("test_initial_scan", self.sample_library)
            scan(context(db, library))
            with Session(db) as session:
                result = [album for (album,) in session.execute(select(AlbumEntity).order_by(AlbumEntity.path)).tuples()]

                assert len(result) == 5
                assert result[0].path == "bar" + os.sep
                assert result[1].path == "baz" + os.sep  # albums were scanned in lexical order

                # flac files
                assert result[0].tracks[0].stream.codec == "FLAC"
                assert len(result[0].tracks) == 3
                assert result[0].tracks[0].file_size > 1
                assert result[0].tracks[0].modify_timestamp > 1
                assert result[0].tracks[0].stream.sample_rate == 44100
                assert result[0].tracks[0].get(BasicTag.TITLE) == ("1",)

                # wma files
                assert result[1].tracks[0].stream.codec == "Windows Media Audio V8"
                assert len(result[1].tracks) == 2
                assert result[1].tracks[0].file_size > 1
                assert result[1].tracks[0].modify_timestamp > 1
                assert result[1].tracks[0].stream.sample_rate == 44100
                assert result[1].tracks[0].get(BasicTag.TITLE) == ("one",)

                # m4a files
                # TODO make sure we know what codec and stream rate is in sample file
                assert len(result[2].tracks) == 2
                assert result[2].tracks[0].file_size > 1
                assert result[2].tracks[0].modify_timestamp > 1
                assert result[2].tracks[0].get(BasicTag.TITLE) == ("one",)

                # mp3 files
                assert result[3].tracks[0].stream.codec == "MP3"
                assert len(result[3].tracks) == 2
                assert result[3].tracks[0].file_size > 1
                assert result[3].tracks[0].modify_timestamp > 1
                assert result[3].tracks[0].stream.sample_rate == 44100
                assert result[3].tracks[0].get(BasicTag.TITLE) == ("1",)

                # aiff files
                assert result[4].tracks[0].stream.codec == "AIFF"
                assert len(result[4].tracks) == 2
                assert result[4].tracks[0].file_size > 1
                assert result[4].tracks[0].modify_timestamp > 1
                assert result[4].tracks[0].stream.sample_rate == 8000
                assert result[4].tracks[0].get(BasicTag.TITLE) == ("one",)

                # image files in folder
                assert len(result[0].picture_files) == 1
                cover_png = result[0].picture_files[0]
                assert cover_png.filename == "cover.jpg"
                assert cover_png.picture_info.mime_type == "image/jpeg"  # because file extension is not correct
                assert cover_png.modify_timestamp
        finally:
            db.dispose()

    def test_scan_empty(self):
        db = connection.open(connection.MEMORY)
        try:
            library = create_library("test_scan_empty", [])
            scan(context(db, library))
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().all()
                assert len(result) == 0
        finally:
            db.dispose()

    def test_scan_no_tags(self):
        db = connection.open(connection.MEMORY)
        try:
            library = create_library(
                "test_scan_no_tags",
                [
                    Album("bar" + os.sep, [Track("1.flac")]),
                    Album("foo" + os.sep, [Track("1.mp3")]),
                    Album("baz" + os.sep, [Track("1.wma")]),
                    Album("foobar" + os.sep, [Track("1.ogg")]),
                ],
            )
            scan(context(db, library))
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().all()
                assert len(result) == 4
        finally:
            db.dispose()

    def test_scan_update(self):
        db = connection.open(connection.MEMORY)
        try:
            library = create_library("test_scan_update", self.sample_library)
            ctx = context(db, library)
            scan(ctx)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity).where(AlbumEntity.path.like("bar%"))).tuples().one()
                assert result[0].tracks[0].filename == "1.flac"
                assert result[0].tracks[0].get(BasicTag.TITLE) == ("1",)

            file = FLAC(library / result[0].path / "1.flac")
            file[BasicTag.TITLE] = "new title"
            file.save()
            scan(ctx)

            with Session(db) as session:
                result = session.execute(select(AlbumEntity).where(AlbumEntity.path.like("bar%"))).tuples().one()
                assert result[0].tracks[0].get(BasicTag.TITLE) == ("new title",)
        finally:
            db.dispose()

    def test_scan_add(self):
        db = connection.open(connection.MEMORY)
        try:
            library = create_library("test_scan_add", [self.sample_library[1]])
            ctx = context(db, library)
            scan(ctx)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().all()
                assert len(result) == 1
                assert result[0][0].path == "foo" + os.sep

            create_album_in_library(library, self.sample_library[0])

            scan(ctx)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity).order_by(AlbumEntity.path)).tuples().all()
                assert len(result) == 2
                assert result[0][0].path == "bar" + os.sep
        finally:
            db.dispose()

    def test_scan_remove_album(self):
        db = connection.open(connection.MEMORY)
        try:
            library = create_library("test_scan_remove", self.sample_library)
            ctx = context(db, library)
            scan(ctx)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity).order_by(AlbumEntity.path)).tuples().all()
                assert len(result) == 5
                assert result[0][0].path == "bar" + os.sep

            # remove a folder that contains an album (removed without scanning)
            shutil.rmtree(library / "bar", ignore_errors=True)
            scan(ctx)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity).order_by(AlbumEntity.path)).tuples().all()
                assert len(result) == 4
                assert result[0][0].path == "baz" + os.sep

            # remove the tracks but the folder is still there (removed when scanned)
            shutil.rmtree(library / "baz", ignore_errors=True)
            os.mkdir(library / "baz")
            scan(ctx)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity).order_by(AlbumEntity.path)).tuples().all()
                assert len(result) == 3
                assert result[0][0].path == "eee" + os.sep
        finally:
            db.dispose()

    def test_scan_remove_picture(self):
        db = connection.open(connection.MEMORY)
        try:
            library = create_library("test_scan_remove_picture", [self.sample_library[0]])
            ctx = context(db, library)
            scan(ctx)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()
                assert len(result[0].picture_files) == 1

            (library / self.sample_library[0].path / "cover.jpg").unlink()

            scan(ctx)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()
                assert len(result[0].picture_files) == 0
        finally:
            db.dispose()

    def test_scan_filtered(self):
        db = connection.open(connection.MEMORY)
        try:
            library = create_library("test_scan_filtered", self.sample_library)
            ctx = context(db, library)
            scan(ctx)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity).order_by(AlbumEntity.path)).tuples().all()
                assert len(result) == 5
                delete_album = result[0][0].path
                shutil.rmtree(library / delete_album, ignore_errors=True)

            scan(ctx, lambda: [(result[1][0].path, result[1][0].album_id)])

            # deleted path was not scanned, so album is still there
            with Session(db) as session:
                result = session.execute(select(AlbumEntity).order_by(AlbumEntity.path)).tuples().all()
                assert len(result) == 5
                assert result[0][0].path == delete_album
        finally:
            db.dispose()

    def test_scanner_version(self):
        db = connection.open(connection.MEMORY)
        try:
            library = create_library("test_scanner_version", self.sample_library[:2])
            ctx = context(db, library)
            scan(ctx)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().all()
                assert len(result) == 2
                assert all(album.scanner == SCANNER_VERSION for [album] in result)

                session.execute(update(AlbumEntity).values(scanner=0))
                session.commit()

            (library / self.sample_library[1].path / self.sample_library[1].tracks[0].filename).unlink()  # second album changed
            create_album_in_library(library, self.sample_library[2])  # third album added
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().all()
                assert len(result) == 2  # third not scanned yet
                assert all(album.scanner == 0 for [album] in result)

            scan(ctx)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().all()
                assert len(result) == 3
                assert all(album.scanner == SCANNER_VERSION for [album] in result)
        finally:
            db.dispose()
