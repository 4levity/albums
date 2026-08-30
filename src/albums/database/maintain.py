"""Post-maintenance of the database: clean up orphaned rows and reclaim disk space."""

import logging
from typing import Final

import humanize
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger: Final = logging.getLogger(__name__)

SQL_CLEANUP: Final = "DELETE FROM collection WHERE collection_id NOT IN (SELECT collection_id FROM album_collection);"


def maintain(db: Engine):
    """Delete orphan collections, log the database size, and VACUUM when wasted space exceeds a threshold."""
    with Session(db) as session:
        session.execute(text(SQL_CLEANUP))

        # determine wasted space in db
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
