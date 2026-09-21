from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.database import MEMORY, db_open
from albums.database.maintain import maintain


class TestMaintain:
    @staticmethod
    def _freelist_count(db) -> int:
        with db.connect() as conn:
            (freelist_count,) = conn.execute(text("SELECT freelist_count FROM pragma_freelist_count;")).one()
        return freelist_count

    def test_deletes_orphan_collections(self):
        db = db_open(MEMORY)
        try:
            with Session(db) as session:
                session.execute(text("INSERT INTO collection (collection_name) VALUES ('orphan');"))
                session.commit()
            maintain(db)
            with Session(db) as session:
                count = session.scalar(text("SELECT count(*) FROM collection;"))
            assert count == 0
        finally:
            db.dispose()

    def test_prunes_scan_history_to_1000_rows(self):
        db = db_open(MEMORY)
        try:
            with Session(db) as session:
                session.execute(
                    text("INSERT INTO scan_history (timestamp, folders_scanned, albums_total) VALUES (:t, :f, :a)"),
                    [{"t": i, "f": i, "a": i} for i in range(1500)],
                )
                session.commit()
            maintain(db)
            with Session(db) as session:
                rows = session.scalars(text("SELECT timestamp FROM scan_history ORDER BY timestamp DESC")).all()
            assert rows == list(range(1499, 499, -1))  # keeps the 1000 most recent rows
        finally:
            db.dispose()

    def test_vacuum_when_wasted_space_is_high(self, tmp_path: Path):
        """db_open must VACUUM a database with high wasted space without a transaction error.

        (This used to raise 'cannot VACUUM from within a transaction'.)
        """
        db_file = tmp_path / "library.db"
        db = db_open(db_file)
        try:
            with db.begin() as conn:
                conn.execute(text("CREATE TABLE junk (data BLOB)"))
                conn.execute(text("INSERT INTO junk VALUES (:data)"), {"data": b"x" * (11 * 1024 * 1024)})  # must exceed 10 MB vacuum threshold
            with db.begin() as conn:
                conn.execute(text("DELETE FROM junk"))
            assert self._freelist_count(db) > 0
        finally:
            db.dispose()

        # reopening the database runs maintain(), which must VACUUM
        db = db_open(db_file)
        try:
            assert self._freelist_count(db) == 0
        finally:
            db.dispose()
