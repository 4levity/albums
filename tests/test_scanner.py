import os
import shutil
from pathlib import Path

from mutagen.flac import FLAC
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from albums.app import SCANNER_VERSION, Context
from albums.database import connection
from albums.database.models import AlbumEntity, PictureFileEntity, TrackEntity, TrackTagEntity
from albums.library.scanner import scan
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger
from albums.types import BasicTag

from .fixtures.create_library import create_album_in_library, create_library, create_picture_file


def context(db: Engine, library: Path):
    context = Context()
    context.db = db
    context.config.library = library
    return context


class TestScanner:
    sample_library = [
        AlbumEntity(
            path="bar" + os.sep,
            tracks=[
                TrackEntity(filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="1")]),
                TrackEntity(filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="2")]),
                TrackEntity(filename="3.flac", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="3")]),
            ],
            picture_files=[PictureFileEntity(filename="cover.jpg", picture_info=PictureInfo("image/png", 410, 410, 24, 0, b""))],
        ),
        AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(filename="1.mp3", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="1")]),
                TrackEntity(filename="2.mp3", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="2")]),
            ],
        ),
        AlbumEntity(
            path="baz" + os.sep,
            tracks=[
                TrackEntity(filename="1.wma", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="one")]),
                TrackEntity(filename="2.wma", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="two")]),
            ],
        ),
        AlbumEntity(
            path="eee" + os.sep,
            tracks=[
                TrackEntity(filename="1.m4a", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="one")]),
                TrackEntity(filename="2.m4a", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="two")]),
            ],
        ),
        AlbumEntity(
            path="mob" + os.sep,
            tracks=[
                TrackEntity(filename="1.aiff", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="one")]),
                TrackEntity(filename="2.aiff", tags=[TrackTagEntity(tag=BasicTag.TITLE, value="two")]),
            ],
        ),
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
                tracks = sorted(result[0].tracks)
                assert len(result[0].tracks) == 3
                assert tracks[0].stream.codec == "FLAC"
                assert tracks[0].file_size > 1
                assert tracks[0].modify_timestamp > 1
                assert tracks[0].stream.sample_rate == 44100
                assert tracks[0].get(BasicTag.TITLE) == ("1",)

                # wma files
                tracks = sorted(result[1].tracks)
                assert len(result[1].tracks) == 2
                assert tracks[0].stream.codec == "Windows Media Audio V8"
                assert tracks[0].file_size > 1
                assert tracks[0].modify_timestamp > 1
                assert tracks[0].stream.sample_rate == 44100
                assert tracks[0].get(BasicTag.TITLE) == ("one",)

                # m4a files
                # TODO make sure we know what codec and stream rate is in sample file
                tracks = sorted(result[2].tracks)
                assert len(result[2].tracks) == 2
                assert tracks[0].file_size > 1
                assert tracks[0].modify_timestamp > 1
                assert tracks[0].get(BasicTag.TITLE) == ("one",)

                # mp3 files
                tracks = sorted(result[3].tracks)
                assert len(result[3].tracks) == 2
                assert tracks[0].stream.codec == "MP3"
                assert tracks[0].file_size > 1
                assert tracks[0].modify_timestamp > 1
                assert tracks[0].stream.sample_rate == 44100
                assert tracks[0].get(BasicTag.TITLE) == ("1",)

                # aiff files
                tracks = sorted(result[4].tracks)
                assert len(result[4].tracks) == 2
                assert tracks[0].stream.codec == "AIFF"
                assert tracks[0].file_size > 1
                assert tracks[0].modify_timestamp > 1
                assert tracks[0].stream.sample_rate == 8000
                assert tracks[0].get(BasicTag.TITLE) == ("one",)

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
                    AlbumEntity(path="bar" + os.sep, tracks=[TrackEntity(filename="1.flac")]),
                    AlbumEntity(path="foo" + os.sep, tracks=[TrackEntity(filename="1.mp3")]),
                    AlbumEntity(path="baz" + os.sep, tracks=[TrackEntity(filename="1.wma")]),
                    AlbumEntity(path="foobar" + os.sep, tracks=[TrackEntity(filename="1.ogg")]),
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
                tracks = sorted(result[0].tracks)
                assert tracks[0].filename == "1.flac"
                assert tracks[0].get(BasicTag.TITLE) == ("1",)

            file = FLAC(library / result[0].path / "1.flac")
            file[BasicTag.TITLE] = "new title"
            file.save()
            scan(ctx)

            with Session(db) as session:
                result = session.execute(select(AlbumEntity).where(AlbumEntity.path.like("bar%"))).tuples().one()
                assert sorted(result[0].tracks)[0].get(BasicTag.TITLE) == ("new title",)
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

                scan(ctx, session, iter([result[1][0]]))

                # deleted path was not scanned, so album is still there
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

    def test_scanner_replace_track(self):
        created_album = self.sample_library[0]
        library = create_library("test_scanner_replace_track", [created_album])
        db = connection.open(connection.MEMORY)
        try:
            ctx = context(db, library)
            with Session(db) as session:
                assert scan(ctx, session) == (1, True)
                (album,) = session.execute(select(AlbumEntity)).tuples().one()
                assert len(album.tracks) == 3
                tracks = sorted(album.tracks)
                assert tracks[0].get(BasicTag.TITLE) == ("1",)
                assert not tracks[0].has(BasicTag.ARTIST)
                track_id = tracks[0].track_id

                with AlbumTagger(library / created_album.path).open(tracks[0].filename) as tags:
                    tags.set_tag(BasicTag.ARTIST, "test replace track")

                assert scan(ctx, session) == (1, True)
                (album,) = session.execute(select(AlbumEntity)).tuples().one()
                assert len(album.tracks) == 3
                tracks = sorted(album.tracks)
                assert tracks[0].get(BasicTag.TITLE) == ("1",)
                assert tracks[0].get(BasicTag.ARTIST) == ("test replace track",)
                assert tracks[1].get(BasicTag.TITLE) == ("2",)
                assert tracks[2].get(BasicTag.TITLE) == ("3",)

                old_track = session.execute(select(TrackEntity).where(TrackEntity.track_id == track_id)).one_or_none()
                assert old_track is None

        finally:
            db.dispose()

    def test_scanner_remove_track(self):
        created_album = self.sample_library[0]
        library = create_library("test_scanner_remove_track", [created_album])
        db = connection.open(connection.MEMORY)
        try:
            ctx = context(db, library)
            with Session(db) as session:
                assert scan(ctx, session) == (1, True)
                (album,) = session.execute(select(AlbumEntity)).tuples().one()
                assert len(album.tracks) == 3
                tracks = sorted(album.tracks)
                assert tracks[0].get(BasicTag.TITLE) == ("1",)
                assert tracks[1].get(BasicTag.TITLE) == ("2",)
                assert tracks[2].get(BasicTag.TITLE) == ("3",)
                track_id = tracks[2].track_id

                os.unlink(library / created_album.path / tracks[2].filename)

                assert scan(ctx, session) == (1, True)
                (album,) = session.execute(select(AlbumEntity)).tuples().one()
                assert len(album.tracks) == 2
                tracks = sorted(album.tracks)
                assert tracks[0].get(BasicTag.TITLE) == ("1",)
                assert tracks[1].get(BasicTag.TITLE) == ("2",)

                old_track = session.execute(select(TrackEntity).where(TrackEntity.track_id == track_id)).one_or_none()
                assert old_track is None

        finally:
            db.dispose()

    def test_scanner_replace_picture_file(self):
        created_album = self.sample_library[0]
        library = create_library("test_scanner_replace_picture_file", [created_album])
        db = connection.open(connection.MEMORY)
        try:
            ctx = context(db, library)
            with Session(db) as session:
                assert scan(ctx, session) == (1, True)
                (album,) = session.execute(select(AlbumEntity)).tuples().one()
                assert len(album.picture_files) == 1
                assert album.picture_files[0].filename == "cover.jpg"
                assert album.picture_files[0].picture_info.width == 410
                picture_file_id = album.picture_files[0].album_picture_file_id

                create_picture_file(library / album.path / "cover.jpg", 123, 321, "pink")

                assert scan(ctx, session) == (1, True)
                (album,) = session.execute(select(AlbumEntity)).tuples().one()
                assert len(album.picture_files) == 1
                assert album.picture_files[0].filename == "cover.jpg"
                assert album.picture_files[0].picture_info.width == 123

                old_picture_file = session.execute(
                    select(PictureFileEntity).where(PictureFileEntity.album_picture_file_id == picture_file_id)
                ).one_or_none()
                assert old_picture_file is None

        finally:
            db.dispose()

    def test_scanner_remove_picture_file(self):
        created_album = self.sample_library[0]
        library = create_library("test_scanner_replace_picture_file", [created_album])
        db = connection.open(connection.MEMORY)
        try:
            ctx = context(db, library)
            with Session(db) as session:
                assert scan(ctx, session) == (1, True)
                (album,) = session.execute(select(AlbumEntity)).tuples().one()
                assert len(album.picture_files) == 1
                assert album.picture_files[0].filename == "cover.jpg"
                assert album.picture_files[0].picture_info.width == 410
                picture_file_id = album.picture_files[0].album_picture_file_id

                os.unlink(library / album.path / "cover.jpg")

                assert scan(ctx, session) == (1, True)
                (album,) = session.execute(select(AlbumEntity)).tuples().one()
                assert len(album.picture_files) == 0

                old_picture_file = session.execute(
                    select(PictureFileEntity).where(PictureFileEntity.album_picture_file_id == picture_file_id)
                ).one_or_none()
                assert old_picture_file is None

        finally:
            db.dispose()
