import logging
import sqlite3
import sys
from pathlib import Path

from albums.database.schema import SQL_INIT_SCHEMA, migrate

logger = logging.getLogger(__name__)

MEMORY = ":memory:"

SQL_INIT_CONNECTION = """
PRAGMA foreign_keys = ON;
"""

SQL_CLEANUP = "DELETE FROM collection WHERE collection_id NOT IN (SELECT collection_id FROM album_collection);"


def open(filename: str):
    new_database = filename == MEMORY or not Path(filename).exists()

    db = sqlite3.connect(filename, autocommit=True)
    db.executescript(SQL_INIT_CONNECTION)
    db.autocommit = False

    if new_database:
        print(f"creating database {filename}")
        with db:
            db.executescript(SQL_INIT_SCHEMA)

    migrate(db)
    with db:
        db.executescript(SQL_CLEANUP)

    return db


def close(db: sqlite3.Connection):
    db.close()
    logger.debug("closed database")


if __name__ == "__main__":
    open(sys.argv[1]).close()  # create empty database for diagram
