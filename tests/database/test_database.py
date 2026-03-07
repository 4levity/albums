import os
import re
from copy import copy
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.database import connection, operations, schema, selector
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

    def test_select_empty(self):
        db = connection.open(connection.MEMORY)
        try:
            result = list(selector.load_albums(db))
            assert len(result) == 0
        finally:
            db.dispose()

    def test_add_and_select(self):
        db = connection.open(connection.MEMORY)
        try:
            album_id = operations.add(db, album)
            assert isinstance(album_id, int)

            assert len(list(selector.load_albums(db))) == 1
            assert len(list(selector.load_albums(db, path=["foo"]))) == 0  # no partial match
            result = list(selector.load_albums(db, path=["foo" + os.sep]))  # exact match
            assert len(result) == 1
            assert result[0].path == "foo" + os.sep
            assert result[0].scanner == 3
            assert sorted(result[0].tracks[0].tags.get(BasicTag.ARTIST, [])) == ["Bar"]
            assert result[0].tracks[0].stream.length == 1.0
            assert result[0].tracks[0].stream.codec == "FLAC"
            assert len(result[0].tracks[0].pictures) == 1
            assert result[0].tracks[0].pictures[0].type == PictureType.COVER_FRONT
            assert result[0].tracks[0].pictures[0].file_info.file_size == 1024

            assert len(result[0].picture_files) == 1
            file = next(file for file in result[0].picture_files if file.filename == "folder.jpg")
            assert file.file_info.mime_type == "test"
            assert file.file_info.width == file.file_info.height == 100
            assert file.file_info.file_size == 4096
            assert file.file_info.file_hash == b"1234"
            assert file.modify_timestamp == 999
            assert file.cover_source
        finally:
            db.dispose()

    def test_select_multiple_and_regex(self):
        album2 = copy(album)
        album2.path = "baz" + os.sep
        album2.collections = []
        db = connection.open(connection.MEMORY)
        try:
            operations.add(db, album)
            operations.add(db, album2)

            re_sep = re.escape(os.sep)
            assert len(list(selector.load_albums(db))) == 2
            assert len(list(selector.load_albums(db, path=["o." + re_sep], regex=True))) == 1  # regex match
            assert len(list(selector.load_albums(db, path=["x." + re_sep], regex=True))) == 0  # no regex match
            assert len(list(selector.load_albums(db, path=["(foo|baz)"], regex=True))) == 2
        finally:
            db.dispose()

    def test_select_by_collection(self):
        album2 = copy(album)
        album2.path = "baz" + os.sep
        album2.collections = []
        db = connection.open(connection.MEMORY)
        try:
            operations.add(db, album)
            operations.add(db, album2)

            assert len(list(selector.load_albums(db))) == 2
            result = list(selector.load_albums(db, collection=["test", "anything"]))
            assert len(result) == 1
            assert result[0].path.startswith("foo")
        finally:
            db.dispose()

    def test_update_collections(self):
        db = connection.open(connection.MEMORY)
        try:
            album_id = operations.add(db, album)
            assert len(list(selector.load_albums(db, collection=["test"]))) == 1
            assert len(list(selector.load_albums(db, collection=["new-collection"]))) == 0

            operations.update_collections(db, album_id, ["new-collection"])

            assert len(list(selector.load_albums(db, collection=["test"]))) == 0
            assert len(list(selector.load_albums(db, collection=["new-collection"]))) == 1
        finally:
            db.dispose()

    def test_update_ignore_checks(self):
        db = connection.open(connection.MEMORY)
        try:
            album_id = operations.add(db, album)
            result = list(selector.load_albums(db))
            assert result[0].ignore_checks == ["artist-tag"]  # initial

            set_ignore_checks = ["album-artist", "cover-filename"]
            operations.update_ignore_checks(db, album_id, set_ignore_checks)
            result = list(selector.load_albums(db))
            assert sorted(result[0].ignore_checks) == set_ignore_checks

            operations.update_ignore_checks(db, album_id, [])  # remove all ignores
            assert list(selector.load_albums(db))[0].ignore_checks == []
        finally:
            db.dispose()

    def test_update_picture_files(self):
        db = connection.open(connection.MEMORY)
        try:
            album_id = operations.add(db, album)
            picture_files = list(selector.load_albums(db))[0].picture_files
            assert len(picture_files) == 1
            assert picture_files[0].cover_source

            # modify existing image file + add one
            file0 = PictureFile(picture_files[0].filename, picture_files[0].file_info, picture_files[0].modify_timestamp, False)
            new_pic_info = PictureInfo("test", 200, 200, 24, 2048, b"abcd")

            operations.update_picture_files(db, album_id, [file0] + list(picture_files[1:]) + [PictureFile("other.jpg", new_pic_info, 999, False)])

            picture_files = list(selector.load_albums(db))[0].picture_files
            pic_folder = next(p for p in picture_files if p.filename == "folder.jpg")
            assert pic_folder
            assert pic_folder.file_info.file_hash == b"1234"
            assert not pic_folder.cover_source
            pic_other = next(p for p in picture_files if p.filename == "other.jpg")
            assert pic_other
            assert pic_other.file_info.mime_type == "test"
            assert pic_other.file_info.width == pic_other.file_info.height == 200
            assert pic_other.file_info.file_size == 2048
            assert pic_other.file_info.file_hash == b"abcd"
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
            assert len(list(selector.load_albums(db))) == 2

            operations.remove(db, album_id)

            result = list(selector.load_albums(db))
            assert len(result) == 1
            assert result[0].path == "baz" + os.sep
        finally:
            db.dispose()

    def test_update_tracks(self):
        db = connection.open(connection.MEMORY)
        try:
            album_id = operations.add(db, album)
            tracks = list(selector.load_albums(db))[0].tracks
            assert len(tracks) == 1

            tracks[0].tags = {BasicTag.ALBUM: ("Foo",)}
            tracks.append(copy(tracks[0]))
            tracks[1].filename = "2.flac"
            operations.update_tracks(db, album_id, tracks)

            tracks = list(selector.load_albums(db))[0].tracks
            assert len(tracks) == 2
            assert all(track.tags[BasicTag.ALBUM] == ("Foo",) for track in tracks)
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
            result = list(selector.load_albums(db))[0]
            assert result.scanner == 3

            operations.update_scanner(db, album_id, 4)

            result = list(selector.load_albums(db))[0]
            assert result.scanner == 4
        finally:
            db.dispose()
