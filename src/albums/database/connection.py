import logging
import sys
from pathlib import Path
from sqlite3 import Connection as SQLite3Connection
from typing import Any

import humanize
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

# don't put any relative imports here, will make this file not runnable
from albums.database.schema import SQL_INIT_SCHEMA, migrate

logger = logging.getLogger(__name__)

MEMORY = ":memory:"

SQL_INIT_CONNECTION = """
PRAGMA foreign_keys = ON;
"""

SQL_CLEANUP = "DELETE FROM collection WHERE collection_id NOT IN (SELECT collection_id FROM album_collection);"


@event.listens_for(Engine, "connect")
def enable_foreign_keys(connection: Any, _):
    if isinstance(connection, SQLite3Connection):
        cursor = connection.cursor()
        cursor.execute(SQL_INIT_CONNECTION)
        cursor.close()


def open(filename: str | Path, echo: bool = False):
    existing_db = Path(filename).exists()
    db = create_engine("sqlite://" if filename == MEMORY else f"sqlite:///{filename}", echo=echo)
    try:
        if filename == MEMORY:
            with db.begin() as conn:
                connection = conn.connection
                connection.executescript(SQL_INIT_SCHEMA)

            migrate(db, True)
        else:
            if existing_db:
                _maintain(db)
            else:
                print(f"creating database {filename}")
                with db.begin() as conn:
                    connection = conn.connection
                    connection.executescript(SQL_INIT_SCHEMA)

            migrate(db, False)
            with Session(db) as session:
                session.execute(text(SQL_CLEANUP))
        return db
    except Exception as ex:
        db.dispose()
        raise ex


def close(db: Engine):
    db.dispose()
    logger.debug("closed database")


def _maintain(db: Engine):
    with Session(db) as session:
        (page_size, page_count, freelist_count) = session.execute(
            text("SELECT page_size, page_count, freelist_count FROM pragma_page_size, pragma_page_count, pragma_freelist_count;")
        ).one()
        size = page_size * page_count
        wasted = page_size * freelist_count
        logger.debug(
            f"database size approx {humanize.naturalsize(size, binary=True)} (wasted space approx {humanize.naturalsize(wasted, binary=True)})"
        )
        # if wasted space is > 10 MB or 20% of the total size, vacuum
        if wasted > max(10 * 1024 * 1024, 0.2 * size):
            logger.debug("vacuuming database")
            session.execute(text("VACUUM;"))


if __name__ == "__main__":
    open(sys.argv[1]).dispose()  # create empty database for diagram
