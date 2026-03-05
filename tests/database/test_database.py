import contextlib
import os
import re
from copy import copy
from pathlib import Path

import pytest

from albums.database import connection, operations, schema, selector
from albums.picture.info import PictureInfo
from albums.tagger.types import Picture, PictureType, StreamInfo
from albums.types import Album, BasicTag, PictureFile, ScanHistoryEntry, Track

embedded_cover = Picture(PictureInfo("image/jpeg", 200, 200, 24, 1024, b"1234"), PictureType.COVER_FRONT, "", (("format", "image/png"),))
track = Track("1.flac", {BasicTag.ARTIST: ["Bar"]}, 0, 0, StreamInfo(1.0, 128000, 2, "FLAC", 44100), [embedded_cover])
folder_jpg = {"folder.jpg": PictureFile(Picture(PictureInfo("test", 100, 100, 24, 4096, b"1234"), PictureType.COVER_FRONT, "", ()), 999, True)}
album = Album("foo" + os.sep, [track], ["test"], ["artist-tag"], folder_jpg, None, 3)


class TestDatabase:
    def test_init_schema(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            schema_version = db.execute("SELECT version FROM _schema;").fetchall()
            assert len(schema_version) == 1
            assert schema_version[0][0] == max(schema.MIGRATIONS.keys()) == (len(schema.MIGRATIONS) + 1) == schema.CURRENT_SCHEMA_VERSION

    def test_foreign_key(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            foreign_keys = db.execute("PRAGMA foreign_keys;").fetchall()
            assert len(foreign_keys) == 1
            assert foreign_keys[0][0] == 1

    def test_schema_too_new(self):
        test_data_path = Path(__file__).resolve().parent / "fixtures" / "libraries"
        os.makedirs(test_data_path, exist_ok=True)
        db_file = test_data_path / "test_database.db"
        if db_file.exists():
            db_file.unlink()
        with contextlib.closing(connection.open(db_file)) as db:
            newer_version = schema.CURRENT_SCHEMA_VERSION + 1
            db.execute("UPDATE _schema SET version = ?;", (newer_version,))
            db.commit()
            assert db.execute("SELECT version FROM _schema;").fetchall()[0][0] == newer_version
        with pytest.raises(RuntimeError):
            with contextlib.closing(connection.open(db_file)) as db:
                assert False  # shouldn't get this far

    def test_select_empty(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            result = list(selector.load_albums(db))
            assert len(result) == 0

    def test_add_and_select(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
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
            file = result[0].picture_files.get("folder.jpg")
            assert file
            assert file.picture.type == PictureType.COVER_FRONT
            assert file.picture.file_info.mime_type == "test"
            assert file.picture.file_info.width == file.picture.file_info.height == 100
            assert file.picture.file_info.file_size == 4096
            assert file.picture.file_info.file_hash == b"1234"
            assert file.modify_timestamp == 999
            assert file.cover_source

    def test_select_multiple_and_regex(self):
        album2 = copy(album)
        album2.path = "baz" + os.sep
        album2.collections = []
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            operations.add(db, album)
            operations.add(db, album2)

            re_sep = re.escape(os.sep)
            assert len(list(selector.load_albums(db))) == 2
            assert len(list(selector.load_albums(db, path=["o." + re_sep], regex=True))) == 1  # regex match
            assert len(list(selector.load_albums(db, path=["x." + re_sep], regex=True))) == 0  # no regex match
            assert len(list(selector.load_albums(db, path=["(foo|baz)"], regex=True))) == 2

    def test_select_by_collection(self):
        album2 = copy(album)
        album2.path = "baz" + os.sep
        album2.collections = []
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            operations.add(db, album)
            operations.add(db, album2)

            assert len(list(selector.load_albums(db))) == 2
            result = list(selector.load_albums(db, collection=["test", "anything"]))
            assert len(result) == 1
            assert result[0].path.startswith("foo")

    def test_update_collections(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            album_id = operations.add(db, album)
            assert len(list(selector.load_albums(db, collection=["test"]))) == 1
            assert len(list(selector.load_albums(db, collection=["new-collection"]))) == 0

            operations.update_collections(db, album_id, ["new-collection"])

            assert len(list(selector.load_albums(db, collection=["test"]))) == 0
            assert len(list(selector.load_albums(db, collection=["new-collection"]))) == 1

    def test_update_ignore_checks(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            album_id = operations.add(db, album)
            result = list(selector.load_albums(db))
            assert result[0].ignore_checks == ["artist-tag"]  # initial

            set_ignore_checks = ["album-artist", "cover-filename"]
            operations.update_ignore_checks(db, album_id, set_ignore_checks)
            result = list(selector.load_albums(db))
            assert sorted(result[0].ignore_checks) == set_ignore_checks

            operations.update_ignore_checks(db, album_id, [])  # remove all ignores
            assert list(selector.load_albums(db))[0].ignore_checks == []

    def test_update_picture_files(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            album_id = operations.add(db, album)
            picture_files = list(selector.load_albums(db))[0].picture_files
            assert len(picture_files) == 1
            assert picture_files["folder.jpg"].cover_source

            # modify existing image file + add one
            picture_files["folder.jpg"].cover_source = False
            new_pic = Picture(PictureInfo("test", 200, 200, 24, 2048, b"abcd"), PictureType.OTHER, "", ())
            operations.update_picture_files(db, album_id, dict(picture_files) | {"other.jpg": PictureFile(new_pic, 999, False)})

            picture_files = list(selector.load_albums(db))[0].picture_files
            pic_folder = picture_files.get("folder.jpg")
            assert pic_folder
            assert pic_folder.picture.type == PictureType.COVER_FRONT
            assert pic_folder.picture.file_info.file_hash == b"1234"
            assert not pic_folder.cover_source
            pic_other = picture_files.get("other.jpg")
            assert pic_other
            assert pic_other.picture.type == PictureType.OTHER
            assert pic_other.picture.file_info.mime_type == "test"
            assert pic_other.picture.file_info.width == pic_other.picture.file_info.height == 200
            assert pic_other.picture.file_info.file_size == 2048
            assert pic_other.picture.file_info.file_hash == b"abcd"

    def test_remove_album(self):
        album2 = copy(album)
        album2.path = "baz" + os.sep
        album2.collections = []
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            album_id = operations.add(db, album)
            operations.add(db, album2)
            assert len(list(selector.load_albums(db))) == 2

            operations.remove(db, album_id)

            result = list(selector.load_albums(db))
            assert len(result) == 1
            assert result[0].path == "baz" + os.sep

    def test_update_tracks(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
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

    def test_scan_history(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            assert operations.get_last_scan_info(db) is None
            operations.record_full_scan(db, ScanHistoryEntry(3, 2, 1))
            entry = operations.get_last_scan_info(db)
            assert entry
            assert entry.timestamp == 3
            assert entry.folders_scanned == 2
            assert entry.albums_total == 1

    def test_update_scanner(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            album_id = operations.add(db, album)
            result = list(selector.load_albums(db))[0]
            assert result.scanner == 3

            operations.update_scanner(db, album_id, 4)

            result = list(selector.load_albums(db))[0]
            assert result.scanner == 4
