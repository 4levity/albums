import os
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from albums.database import connection, schema
from albums.types import Album, BasicTag, Track


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

    def test_album_created_at(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                album = Album(path="foo" + os.sep)
                session.add(album)
                session.flush()
                assert album.created_at > 1_000_000_000
                session.commit()
        finally:
            db.dispose()

    def test_album_modified_at_default(self):
        album = Album(path="foo" + os.sep)
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(album)
                session.flush()

                (album,) = session.execute(select(Album)).tuples().one()
                assert album.modified_at > 1_000_000_000
                session.commit()
        finally:
            db.dispose()

    def test_unknown_tag_in_db(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicTag.ALBUM: "foo"})])
                session.add(album)
                session.flush()
                track_id = album.tracks[0].track_id
                session.commit()
            with db.begin() as conn:
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track_id}, 'invalid1', 'bar');"))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track_id}, 'invalid2', 'baz');"))
            with Session(db) as session:
                (album,) = session.execute(select(Album)).tuples().one()
                tag = album.tracks[0].tag_dict()
                assert len(tag) == 2
                assert tag[BasicTag.ALBUM] == ["foo"]
                assert sorted(tag[BasicTag.UNKNOWN]) == ["bar", "baz"]
        finally:
            db.dispose()
