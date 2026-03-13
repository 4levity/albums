import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.database import connection, schema


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
