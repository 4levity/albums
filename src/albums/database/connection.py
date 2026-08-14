import logging
import sys
from pathlib import Path
from sqlite3 import Connection as SQLite3Connection
from typing import Any, Final

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

# don't put any relative imports here, will make this file not runnable
from albums.database.maintain import maintain
from albums.database.migrations import get_init_schema, migrate

logger: Final = logging.getLogger(__name__)

# Sentinel for in-memory database
MEMORY: Final = ":memory:"


@event.listens_for(Engine, "connect")
def enable_foreign_keys(connection: Any, _):
    if isinstance(connection, SQLite3Connection):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()


def db_open(filename: str | Path, echo: bool = False, version: int | None = None):
    """Open or create a database.

    Args:
        filename: Database file path, or MEMORY for in-memory.
        echo: Enable SQLAlchemy query logging.
        version: If specified, create/migrate the database to this version instead of the latest.
            Useful for tests that need to test specific migrations.

    Returns:
        SQLAlchemy Engine.
    """
    existing_db = Path(filename).exists()
    db = create_engine("sqlite://" if filename == MEMORY else f"sqlite:///{filename}", echo=echo)
    try:
        if filename == MEMORY:
            with db.begin() as conn:
                connection = conn.connection
                connection.executescript(get_init_schema())

            migrate(db, True, target_version=version)
        else:
            if not existing_db:
                print(f"creating database {filename}")
                with db.begin() as conn:
                    connection = conn.connection
                    connection.executescript(get_init_schema())

            migrate(db, False, target_version=version)
            maintain(db)
        return db
    except Exception as ex:
        # Ensure all connections are disposed on error to prevent resource warnings
        try:
            db.dispose()
        except Exception as ex1:
            logger.warning(repr(ex1))
        raise ex


if __name__ == "__main__":
    db_open(sys.argv[1]).dispose()  # create empty database for diagram
