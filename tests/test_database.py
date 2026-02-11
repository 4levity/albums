import contextlib

from albums.database import connection, operations, schema, selector
from albums.types import Album, Picture, PictureType, ScanHistoryEntry, Stream, Track


class TestDatabase:
    def test_init_schema(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            schema_version = db.execute("SELECT version FROM _schema;").fetchall()
            assert len(schema_version) == 1
            assert schema_version[0][0] == max(schema.MIGRATIONS.keys())

    def test_foreign_key(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            foreign_keys = db.execute("PRAGMA foreign_keys;").fetchall()
            assert len(foreign_keys) == 1
            assert foreign_keys[0][0] == 1

    def test_operations(self):
        # TODO this test needs to be split up!

        def track(filename="1.flac"):
            return Track(
                filename,
                {"title": ["foo", "bar"]},
                1,
                0,
                Stream(1.5, 0, 0, "FLAC"),
                [Picture(PictureType.COVER_FRONT, "test", 4, 5, 6, b"", None, None, 1)],
            )

        albums = [
            Album("foo/", [track()]),
            Album(
                "bar/",
                [track()],
                ["test"],
                ["artist_tag"],
                {"folder.jpg": Picture(PictureType.COVER_FRONT, "test", 100, 100, 1024, b"1234", None, 999, 0, True)},
                None,
                3,
            ),
        ]

        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 0
            albums[0].album_id = operations.add(db, albums[0])
            assert isinstance(albums[0].album_id, int)
            albums[1].album_id = operations.add(db, albums[1])
            assert len(list(selector.select_albums(db, [], [], False))) == 2  # all
            assert len(list(selector.select_albums(db, [], ["foo/"], False))) == 1  # exact match
            assert len(list(selector.select_albums(db, [], ["oo/"], False))) == 0  # no partial match
            assert len(list(selector.select_albums(db, [], ["o./"], True))) == 1  # regex match
            assert len(list(selector.select_albums(db, [], ["x./"], True))) == 0  # no regex match

            result = list(selector.select_albums(db, ["test", "anything"], [], False))
            assert len(result) == 1  # initial collection
            assert result[0].path == "bar/"
            assert result[0].scanner == 3
            assert sorted(result[0].tracks[0].tags.get("title", [])) == ["bar", "foo"]
            assert result[0].tracks[0].stream.length == 1.5
            assert result[0].tracks[0].stream.codec == "FLAC"
            assert len(result[0].tracks[0].pictures) == 1
            assert result[0].tracks[0].pictures[0].picture_type == PictureType.COVER_FRONT
            assert result[0].tracks[0].pictures[0].file_size == 6
            assert result[0].tracks[0].pictures[0].embed_ix == 1

            assert len(result[0].picture_files) == 1
            pic = result[0].picture_files.get("folder.jpg")
            assert pic
            assert pic.picture_type == PictureType.COVER_FRONT
            assert pic.format == "test"
            assert pic.width == pic.height == 100
            assert pic.file_size == 1024
            assert pic.file_hash == b"1234"
            assert pic.modify_timestamp == 999
            assert pic.front_cover_source

            assert len(list(selector.select_albums(db, [], ["/"], True))) == 2  # regex match all
            assert len(list(selector.select_albums(db, ["test", "anything"], ["/"], True))) == 1  # regex + collection match

            operations.update_collections(db, albums[0].album_id, ["test"])
            assert len(list(selector.select_albums(db, ["test", "anything"], [], False))) == 2  # added to collection

            operations.update_collections(db, albums[1].album_id, [])
            result = list(selector.select_albums(db, ["test", "anything"], [], False))
            assert len(result) == 1  # removed from collection
            assert result[0].path == "foo/"

            set_ignore_checks = ["album_artist", "required_tags"]
            operations.update_ignore_checks(db, albums[0].album_id, set_ignore_checks)
            result = list(selector.select_albums(db, [], [albums[0].path], False))
            assert len(result) == 1
            assert sorted(result[0].ignore_checks) == set_ignore_checks

            operations.update_ignore_checks(db, albums[0].album_id, [])
            result = list(selector.select_albums(db, [], [albums[0].path], False))
            assert len(result) == 1
            assert result[0].ignore_checks == []

            cover = Picture(PictureType.OTHER, "test", 200, 200, 2048, b"abcd", None, 999)
            albums[1].picture_files["other.jpg"] = cover
            assert albums[1].picture_files["folder.jpg"].front_cover_source
            albums[1].picture_files["folder.jpg"].front_cover_source = False
            operations.update_picture_files(db, albums[1].album_id, albums[1].picture_files)
            result = list(selector.select_albums(db, [], [albums[1].path], False))
            assert len(result[0].picture_files) == 2
            pic_folder = result[0].picture_files.get("folder.jpg")
            assert pic_folder
            assert not pic_folder.front_cover_source
            pic_other = result[0].picture_files.get("other.jpg")
            assert pic_other

            assert pic_folder.picture_type == PictureType.COVER_FRONT
            assert pic_other.picture_type == PictureType.OTHER
            assert pic_other.format == "test"
            assert pic_other.width == pic_other.height == 200
            assert pic_other.file_size == 2048
            assert pic_folder.file_hash == b"1234"
            assert pic_other.file_hash == b"abcd"

            operations.remove(db, albums[1].album_id)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result) == 1  # album removed
            assert result[0].path == "foo/"

            assert len(result[0].tracks) == 1
            albums[0].tracks.append(track("2.flac"))
            operations.update_tracks(db, albums[0].album_id, albums[0].tracks)
            result = list(selector.select_albums(db, [], [], False))
            assert len(result[0].tracks) == 2

            assert operations.get_last_scan_info(db) is None
            operations.record_full_scan(db, ScanHistoryEntry(3, 2, 1))
            entry = operations.get_last_scan_info(db)
            assert entry
            assert entry.timestamp == 3
            assert entry.folders_scanned == 2
            assert entry.albums_total == 1

            result = list(selector.select_albums(db, [], [albums[0].path], False))
            assert result[0].scanner == 0
            operations.update_scanner(db, albums[0].album_id, 4)
            result = list(selector.select_albums(db, [], [albums[0].path], False))
            assert result[0].scanner == 4
