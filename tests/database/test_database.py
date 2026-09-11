import os
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from albums.database import MEMORY, db_open
from albums.entities import Album, Track
from albums.tagger import BasicField


class TestDatabase:
    def test_init_schema(self):
        db = db_open(MEMORY)
        try:
            with Session(db) as session:
                schema_version = session.scalar(text("SELECT version FROM _schema;"))
            assert schema_version > 17  # proves that schema is in place and multiple migrations applied
        finally:
            db.dispose()

    def test_foreign_key(self):
        db = db_open(MEMORY)
        try:
            with Session(db) as session:
                foreign_keys = session.scalar(text("PRAGMA foreign_keys;"))
            assert foreign_keys == 1
        finally:
            db.dispose()

    def test_schema_too_new(self, tmp_path: Path):
        db_file = tmp_path / "test_database.db"
        db = db_open(db_file)
        try:
            with Session(db) as session:
                current_version = session.scalar(text("SELECT version FROM _schema;"))
                newer_version = current_version + 1
                session.execute(text("UPDATE _schema SET version = :version ;"), {"version": newer_version})
                session.commit()
                assert session.scalar(text("SELECT version FROM _schema;")) == newer_version
        finally:
            db.dispose()

        with pytest.raises(RuntimeError):
            db_open(db_file)
            assert False  # shouldn't get this far

    def test_album_created_at(self):
        db = db_open(MEMORY)
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
        db = db_open(MEMORY)
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
        db = db_open(MEMORY)
        try:
            with Session(db) as session:
                album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "foo"})])
                session.add(album)
                session.flush()
                track_id = album.tracks[0].track_id
                session.commit()
            with db.begin() as conn:
                conn.execute(text(f"INSERT INTO track_field (track_id, name, value) VALUES ({track_id}, 'invalid1', 'bar');"))
                conn.execute(text(f"INSERT INTO track_field (track_id, name, value) VALUES ({track_id}, 'invalid2', 'baz');"))
            with Session(db) as session:
                (album,) = session.execute(select(Album)).tuples().one()
                tag = album.tracks[0].field_dict()
                assert len(tag) == 2
                assert tag[BasicField.ALBUM] == ["foo"]
                assert sorted(tag[BasicField.UNKNOWN]) == ["bar", "baz"]
        finally:
            db.dispose()
