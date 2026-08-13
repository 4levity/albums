"""Database schema migrations loaded from individual SQL files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from albums.database.orm import schema_table

logger: Final = logging.getLogger(__name__)

_MIGRATIONS_DIR: Final = Path(__file__).parent


def get_init_schema() -> str:
    """Get the initial schema SQL (need to run migrations)"""
    with (_MIGRATIONS_DIR / "01_init.sql").open("r") as f:
        return f.read()


def _load_migrations() -> dict[int, str]:
    """Load all migration SQL files keyed by version number."""
    result: dict[int, str] = {}
    for sql_file in sorted(_MIGRATIONS_DIR.iterdir()):
        stem = sql_file.stem
        if not stem.isdigit():
            continue
        version = int(stem)
        with sql_file.open("r") as f:
            result[version] = f.read()
    return result


def migrate(db: Engine, quiet: bool = False, target_version: int | None = None) -> None:
    """Run all required migrations up to *target_version* (or the latest). Some schema must be present.

    Args:
        db: SQLAlchemy engine connected to the SQLite database.
        quiet: Suppress migration log messages.
        target_version: Target schema version.  Pass ``None`` (default) for
            the latest available version.
    """
    migrations = _load_migrations()
    current_schema_version = max(migrations.keys())
    effective_target = target_version if target_version is not None else current_schema_version

    with Session(db) as session:
        db_version = int(str(session.scalar(select(schema_table.c.version))))
    if db_version > current_schema_version:
        raise RuntimeError(f"the database is newer than this version of albums ({db_version} > {current_schema_version})")
    if db_version > effective_target:
        raise ValueError(f"the database is newer than the target database version ({db_version} > {effective_target})")
    if db_version == effective_target:
        return

    range_to_run = range(db_version + 1, effective_target + 1)
    if not quiet:
        logger.debug("database schema version %d, migrations to perform: %s", db_version, list(range_to_run))

    for version in range_to_run:
        if not quiet:
            logger.info("migrating database: v%d", version)
        with db.begin() as conn:
            conn.connection.executescript(migrations[version])

    with Session(db) as session:
        session.execute(update(schema_table), {"version": effective_target})
        session.commit()
