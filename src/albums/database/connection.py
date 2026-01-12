import logging
from pathlib import Path
import sqlite3

from .migration import migrate
from .schema import SQL_INIT_SCHEMA


logger = logging.getLogger(__name__)

SQL_INIT_CONNECTION = """
PRAGMA foreign_keys = ON;
"""

SQL_CLEANUP = "DELETE FROM collection WHERE collection_id NOT IN (SELECT collection_id FROM album_collection);"


def open(filename: str):
    new_database = filename == ":memory:" or not Path(filename).exists()

    # TODO switch to explicit transactions
    db = sqlite3.connect(filename)
    db.executescript(SQL_INIT_CONNECTION)
    if new_database:
        print(f"creating database {filename}")
        db.executescript(SQL_INIT_SCHEMA)

    migrate(db)
    db.executescript(SQL_CLEANUP)
    return db


def close(db: sqlite3.Connection):
    db.commit()
    db.close()
    logger.debug("closed database")
