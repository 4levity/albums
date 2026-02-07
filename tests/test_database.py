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
        def track(filename="1.flac"):
            return Track(
                filename, {"title": ["foo", "bar"]}, 1, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "test", 4, 5, 6, b"")]
            )

        albums = [Album("foo/", [track()], []), Album("bar/", [track()], ["test"])]

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
            assert sorted(result[0].tracks[0].tags.get("title", [])) == ["bar", "foo"]
            assert result[0].tracks[0].stream.length == 1.5
            assert result[0].tracks[0].stream.codec == "FLAC"
            assert len(result[0].tracks[0].pictures) == 1
            assert result[0].tracks[0].pictures[0].picture_type == PictureType.COVER_FRONT
            assert result[0].tracks[0].pictures[0].file_size == 6

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
