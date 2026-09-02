"""Cross-cutting tests over the whole migration chain (all of 01-18)."""

import pytest
from sqlalchemy import text

from albums.config import SettingEntity  # noqa: F401  (registers the setting table on Base.metadata)
from albums.database import MEMORY, db_open, migrate
from albums.database.migrations.migrate import _load_migrations
from albums.database.orm import Base
from albums.entities import Album, Track  # noqa: F401  (registers the ORM models)


class TestSchemaConsistency:
    """The fully-migrated database must match what the ORM models expect.

    A single test over the whole chain catches column/index drift introduced by any migration,
    without needing per-migration DDL tests.
    """

    @staticmethod
    def _orm_tables():
        return list(Base.metadata.tables.values())

    def test_final_schema_matches_orm(self):
        """Every ORM table's columns (name, nullability, primary key), foreign keys and indexes
        must exist in the fully-migrated database."""
        db = db_open(MEMORY)
        try:
            for table in self._orm_tables():
                with db.connect() as conn:
                    db_columns = conn.execute(text(f"PRAGMA table_info({table.name});")).fetchall()
                    db_fks = conn.execute(text(f"PRAGMA foreign_key_list({table.name});")).fetchall()
                    db_indexes = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='index';"))}

                db_column_map = {r[1]: r for r in db_columns}  # name -> (cid, name, type, notnull, default_value, pk)
                for column in table.columns:
                    assert column.name in db_column_map, f"{table.name}: ORM column {column.name!r} missing from migrated schema"
                    db_column = db_column_map[column.name]
                    assert bool(db_column[5]) == column.primary_key, f"{table.name}.{column.name}: primary key mismatch"
                    # The DB may be *looser* than the ORM (migrations often omit NOT NULL on FK
                    # columns, and SQLite reports notnull=0 for INTEGER PRIMARY KEY rowid aliases),
                    # but never stricter: a NOT NULL the ORM doesn't declare would reject ORM writes.
                    assert bool(db_column[3]) <= bool(not column.nullable), (
                        f"{table.name}.{column.name}: DB enforces NOT NULL but the ORM column is nullable"
                    )

                # Every ORM-declared index must exist in the migrated schema
                for index in table.indexes:
                    assert index.name in db_indexes, f"{table.name}: ORM index {index.name!r} missing from migrated schema"

                # Every ORM foreign key must be present in the migrated schema
                db_fk_refs = {(fk[2], fk[4] or fk[3]) for fk in db_fks}  # (referenced table, referenced column)
                for fk in table.foreign_key_constraints:
                    for column in fk.columns:
                        target = next(iter(column.foreign_keys)).target_fullname
                        referenced_table, referenced_column = target.split(".")
                        assert (referenced_table, referenced_column) in db_fk_refs, (
                            f"{table.name}.{column.name}: foreign key to {target} missing from migrated schema"
                        )
        finally:
            db.dispose()

    def test_all_versions_migratable(self):
        """Every schema version from the initial schema up to the latest must be reachable,
        i.e. each migration applies cleanly to the schema left by all previous ones."""
        migrations = _load_migrations()
        latest = max(migrations.keys())
        for version in range(2, latest + 1):
            db = db_open(MEMORY, version=version)
            try:
                assert db.connect().execute(text("SELECT version FROM _schema;")).scalar() == version
            finally:
                db.dispose()
        # db_open with an explicit version also works for the initial schema
        with pytest.raises((ValueError, RuntimeError)):
            # sanity: a version below the initial schema is rejected, not silently accepted
            db_open(MEMORY, version=0)

    def test_migrate_to_specific_target(self):
        """migrate() must stop at the requested version and record exactly that version."""
        db = db_open(MEMORY, version=15)
        try:
            migrate(db, quiet=True, target_version=16)
            assert db.connect().execute(text("SELECT version FROM _schema;")).scalar() == 16
            # and again: already at target -> no-op
            migrate(db, quiet=True, target_version=16)
            assert db.connect().execute(text("SELECT version FROM _schema;")).scalar() == 16
        finally:
            db.dispose()

    def test_target_version_too_new_rejected(self):
        """Requesting a version newer than the latest available must raise, not KeyError."""
        db = db_open(MEMORY)
        try:
            with pytest.raises(ValueError, match="newer than the latest"):
                migrate(db, quiet=True, target_version=99)
        finally:
            db.dispose()

    def test_migrations_loaded_from_files(self):
        """The migration files must be complete and ordered: versions 1..N with no gaps."""
        migrations = _load_migrations()
        assert sorted(migrations.keys()) == list(range(2, 2 + len(migrations)))
        assert all(sql.strip() for sql in migrations.values())
