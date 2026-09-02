from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.database import MEMORY, db_open, migrate


class TestMigration11CollectionRecreate:
    """Test that migration 11 recreates the collection table (adding ON CONFLICT IGNORE to the unique
    constraint on collection_name) without losing data or breaking foreign keys."""

    def test_collections_and_associations_preserved(self):
        """Collections and album<->collection associations must survive the table recreation.

        The DROP TABLE collection in the migration would cascade-delete album_collection rows
        if foreign key enforcement were not turned off first, so this also guards against that.
        """
        db = db_open(MEMORY, version=10)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES ('album1/');"))
                conn.execute(text("INSERT INTO album (path) VALUES ('album2/');"))
                conn.execute(text("INSERT INTO collection (collection_name) VALUES ('playlists');"))
                conn.execute(text("INSERT INTO collection (collection_name) VALUES ('favorites');"))
                conn.execute(text("INSERT INTO album_collection (album_id, collection_id) VALUES (1, 1);"))
                conn.execute(text("INSERT INTO album_collection (album_id, collection_id) VALUES (2, 2);"))

            # Migrate v10 -> v11 only
            migrate(db, quiet=True, target_version=11)

            with Session(db) as session:
                collections = session.execute(text("SELECT collection_id, collection_name FROM collection ORDER BY collection_id;")).fetchall()
                assert len(collections) == 2
                assert (1, "playlists") in [(r.collection_id, r.collection_name) for r in collections]
                assert (2, "favorites") in [(r.collection_id, r.collection_name) for r in collections]

                associations = session.execute(text("SELECT album_id, collection_id FROM album_collection ORDER BY album_id;")).fetchall()
                assert [(r.album_id, r.collection_id) for r in associations] == [(1, 1), (2, 2)]
        finally:
            db.dispose()

    def test_foreign_key_cascade_still_works(self):
        """After the rename, deleting a collection should cascade-delete its album_collection rows."""
        db = db_open(MEMORY, version=10)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES ('album1/');"))
                conn.execute(text("INSERT INTO collection (collection_name) VALUES ('playlists');"))
                conn.execute(text("INSERT INTO album_collection (album_id, collection_id) VALUES (1, 1);"))

            migrate(db, quiet=True, target_version=11)

            # FK enforcement must be back on after the migration's PRAGMA toggles
            assert db.connect().execute(text("PRAGMA foreign_keys;")).scalar() == 1

            with Session(db) as session:
                session.execute(text("DELETE FROM collection WHERE collection_id = 1;"))
                session.commit()
                associations = session.execute(text("SELECT COUNT(*) FROM album_collection;")).scalar()
                assert associations == 0  # cascade deleted
        finally:
            db.dispose()

    def test_duplicate_name_ignored(self):
        """The whole point of migration 11: inserting a duplicate collection name is ignored, not an error."""
        db = db_open(MEMORY, version=10)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO collection (collection_name) VALUES ('playlists');"))

            migrate(db, quiet=True, target_version=11)

            # Before migration 11 this raised IntegrityError
            with Session(db) as session:
                session.execute(text("INSERT INTO collection (collection_name) VALUES ('playlists');"))
                session.commit()
                rows = session.execute(text("SELECT collection_name FROM collection;")).fetchall()
                assert len(rows) == 1
        finally:
            db.dispose()
