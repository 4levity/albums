import os
from copy import copy
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from albums.database import connection, operations, schema
from albums.database.models import AlbumEntity
from albums.picture.info import PictureInfo
from albums.tagger.types import Picture, PictureType, StreamInfo
from albums.types import Album, BasicTag, PictureFile, ScanHistoryEntry, Track

embedded_cover = Picture(PictureInfo("image/jpeg", 200, 200, 24, 1024, b"1234", (("format", "image/png"),)), PictureType.COVER_FRONT, "")
track = Track("1.flac", {BasicTag.ARTIST: ["Bar"]}, 0, 0, StreamInfo(1.0, 128000, 2, "FLAC", 44100), [embedded_cover])
folder_jpg = PictureFile("folder.jpg", PictureInfo("test", 100, 100, 24, 4096, b"1234"), 999, True)
album = Album("foo" + os.sep, [track], ["test"], ["artist-tag"], [folder_jpg], None, 3)


class TestDatabase:
    def test_init_schema(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                schema_version = session.scalar(text("SELECT version FROM _schema;"))
            assert schema_version == max(schema.MIGRATIONS.keys()) == (len(schema.MIGRATIONS) + 1) == schema.CURRENT_SCHEMA_VERSION
        finally:
            db.dispose()

    def test_foreign_key(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                foreign_keys = session.scalar(text("PRAGMA foreign_keys;"))
            assert foreign_keys == 1
        finally:
            db.dispose()

    def test_schema_too_new(self):
        test_data_path = Path(__file__).resolve().parent / "fixtures" / "libraries"
        os.makedirs(test_data_path, exist_ok=True)
        db_file = test_data_path / "test_database.db"
        if db_file.exists():
            db_file.unlink()
        db = connection.open(db_file)
        try:
            with Session(db) as session:
                newer_version = schema.CURRENT_SCHEMA_VERSION + 1
                session.execute(text("UPDATE _schema SET version = :version ;"), {"version": newer_version})
                session.commit()
                assert session.scalar(text("SELECT version FROM _schema;")) == newer_version
            with pytest.raises(RuntimeError):
                connection.open(db_file)
                assert False  # shouldn't get this far
        finally:
            db.dispose()

    def test_update_collections(self):
        db = connection.open(connection.MEMORY)
        try:
            album_id = operations.add(db, album)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                assert any(c == "test" for c in result.collections)
                assert not any(c == "new-collection" for c in result.collections)

            operations.update_collections(db, album_id, ["new-collection"])

            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                assert not any(c == "test" for c in result.collections)
                assert any(c == "new-collection" for c in result.collections)
        finally:
            db.dispose()

    def test_update_ignore_checks(self):
        db = connection.open(connection.MEMORY)
        try:
            album_id = operations.add(db, album)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                assert result.ignore_checks == ["artist-tag"]  # initial

            set_ignore_checks = ["album-artist", "cover-filename"]
            operations.update_ignore_checks(db, album_id, set_ignore_checks)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                assert sorted(result.ignore_checks) == set_ignore_checks

            operations.update_ignore_checks(db, album_id, [])  # remove all ignores
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                assert result.ignore_checks == []
        finally:
            db.dispose()

    def test_update_picture_files(self):
        db = connection.open(connection.MEMORY)
        try:
            album_id = operations.add(db, album)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                picture_files = [operations.picture_file_from_entity(f) for f in result.picture_files]
                assert len(picture_files) == 1
                assert picture_files[0].cover_source

                # modify existing image file + add one
                file0 = PictureFile(picture_files[0].filename, picture_files[0].picture_info, picture_files[0].modify_timestamp, False)
                new_pic_info = PictureInfo("test", 200, 200, 24, 2048, b"abcd")

            operations.update_picture_files(db, album_id, [file0] + list(picture_files[1:]) + [PictureFile("other.jpg", new_pic_info, 999, False)])

            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                picture_files = [operations.picture_file_from_entity(f) for f in result.picture_files]
            pic_folder = next(p for p in picture_files if p.filename == "folder.jpg")
            assert pic_folder
            assert pic_folder.picture_info.file_hash == b"1234"
            assert not pic_folder.cover_source
            pic_other = next(p for p in picture_files if p.filename == "other.jpg")
            assert pic_other
            assert pic_other.picture_info.mime_type == "test"
            assert pic_other.picture_info.width == pic_other.picture_info.height == 200
            assert pic_other.picture_info.file_size == 2048
            assert pic_other.picture_info.file_hash == b"abcd"
        finally:
            db.dispose()

    def test_remove_album(self):
        album2 = copy(album)
        album2.path = "baz" + os.sep
        album2.collections = []
        db = connection.open(connection.MEMORY)
        try:
            album_id = operations.add(db, album)
            operations.add(db, album2)
            with Session(db) as session:
                assert len(session.execute(select(AlbumEntity)).all()) == 2

            operations.remove(db, album_id)

            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().all()
                assert len(result) == 1
                assert result[0][0].path == "baz" + os.sep
        finally:
            db.dispose()

    def test_update_tracks(self):
        db = connection.open(connection.MEMORY)
        try:
            album_id = operations.add(db, album)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                tracks = [operations.track_from_entity(t) for t in result.tracks]
            assert len(tracks) == 1

            tracks[0].tags = {BasicTag.ALBUM: ("Foo",)}
            tracks.append(copy(tracks[0]))
            tracks[1].filename = "2.flac"
            operations.update_tracks(db, album_id, tracks)

            with Session(db) as session:
                tracks = session.execute(select(AlbumEntity)).tuples().one()[0].tracks
                assert len(tracks) == 2
                assert all(track.get(BasicTag.ALBUM) == ("Foo",) for track in tracks)
        finally:
            db.dispose()

    def test_scan_history(self):
        db = connection.open(connection.MEMORY)
        try:
            assert operations.get_last_scan_info(db) is None
            operations.record_full_scan(db, ScanHistoryEntry(3, 2, 1))
            entry = operations.get_last_scan_info(db)
            assert entry
            assert entry.timestamp == 3
            assert entry.folders_scanned == 2
            assert entry.albums_total == 1
        finally:
            db.dispose()

    def test_update_scanner(self):
        db = connection.open(connection.MEMORY)
        try:
            album_id = operations.add(db, album)
            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                assert result.scanner == 3

            operations.update_scanner(db, album_id, 4)

            with Session(db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                assert result.scanner == 4
        finally:
            db.dispose()
