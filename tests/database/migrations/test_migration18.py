from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.database import connection
from albums.database.migrations import migrate
from albums.tagger import BasicField

from .sql_helpers import make_track_sql


class TestMigration18TableNameRenamed:
    """Test that migration 18 renames track_tag to track_field and related objects."""

    def test_track_tag_renamed_to_track_field(self):
        """Test that track_tag table is renamed to track_field with data preserved."""
        db = connection.db_open(connection.MEMORY, version=17)
        try:
            # Insert rows into old track_tag table using raw SQL
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES ('test_album');"))
                conn.execute(text(make_track_sql(1, "1.flac")))
                # track_tag rows (old name) - use lowercase field names as stored in DB
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ARTIST.value}', 'TestArtist');"))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ALBUM.value}', 'TestAlbum');"))

            # Migrate v17 -> v18
            migrate(db, quiet=True, target_version=18)

            # Verify old table is gone
            with Session(db) as session:
                tables = session.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")).fetchall()
                table_names = [r.name for r in tables]
                assert "track_tag" not in table_names
                assert "track_field" in table_names

            # Verify data preserved
            with Session(db) as session:
                rows = session.execute(text("SELECT track_id, name, value FROM track_field ORDER BY name;")).fetchall()
                assert len(rows) == 2
                assert (1, BasicField.ALBUM.value, "TestAlbum") in [(r.track_id, r.name, r.value) for r in rows]
                assert (1, BasicField.ARTIST.value, "TestArtist") in [(r.track_id, r.name, r.value) for r in rows]
        finally:
            db.dispose()

    def test_track_legacy_tag_renamed_to_track_legacy_field(self):
        """Test that track_legacy_tag table is renamed to track_legacy_field with column rename."""
        db = connection.db_open(connection.MEMORY, version=17)
        try:
            # Insert a minimal album + track
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES ('test_album');"))
                conn.execute(text(make_track_sql(1, "1.flac")))
                # track_legacy_tag row with old column name (tag_name)
                conn.execute(text("INSERT INTO track_legacy_tag (track_id, tag_name) VALUES (1, 'legacy_vorbis_comment');"))

            # Migrate v17 -> v18
            migrate(db, quiet=True, target_version=18)

            # Verify old table gone, new table exists
            with Session(db) as session:
                tables = session.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")).fetchall()
                table_names = [r.name for r in tables]
                assert "track_legacy_tag" not in table_names
                assert "track_legacy_field" in table_names

            # Verify data preserved with column renamed (tag_name -\u003e field_name)
            with Session(db) as session:
                rows = session.execute(text("SELECT track_id, field_name FROM track_legacy_field ORDER BY track_id;")).fetchall()
                assert len(rows) == 1
                assert rows[0].track_id == 1
                assert rows[0].field_name == "legacy_vorbis_comment"
        finally:
            db.dispose()

    def test_indexes_renamed(self):
        """Test that old indexes are gone and new ones exist."""
        db = connection.db_open(connection.MEMORY, version=17)
        try:
            # Insert data to make sure tables/indexes have rows
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES ('test_album');"))
                conn.execute(text(make_track_sql(1, "1.flac")))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ARTIST.value}', 'A');"))
                conn.execute(text("INSERT INTO track_legacy_tag (track_id, tag_name) VALUES (1, 'old_field');"))

            # Migrate v17 -> v18
            migrate(db, quiet=True, target_version=18)

            # Check indexes
            with Session(db) as session:
                indexes = session.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' ORDER BY name;")).fetchall()
                index_names = [r.name for r in indexes]
                # Old indexes should be gone
                assert "idx_track_tag_track_id" not in index_names
                assert "idx_legacy_tag_track_id" not in index_names
                # New indexes should exist
                assert "idx_track_field_track_id" in index_names
                assert "idx_legacy_field_track_id" in index_names
        finally:
            db.dispose()

    def test_pk_columns_renamed(self):
        """Test that primary key columns are renamed correctly."""
        db = connection.db_open(connection.MEMORY, version=17)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES ('test_album');"))
                conn.execute(text(make_track_sql(1, "1.flac")))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ARTIST.value}', 'A');"))
                conn.execute(text("INSERT INTO track_legacy_tag (track_id, tag_name) VALUES (1, 'old_field');"))

            migrate(db, quiet=True, target_version=18)

            # Check that new PK column names exist by inspecting table info
            with Session(db) as session:
                track_field_cols = session.execute(text("PRAGMA table_info(track_field);")).fetchall()
                track_field_col_names = [r.name for r in track_field_cols]
                assert "track_field_id" in track_field_col_names
                assert "track_tag_id" not in track_field_col_names

                legacy_field_cols = session.execute(text("PRAGMA table_info(track_legacy_field);")).fetchall()
                legacy_field_col_names = [r.name for r in legacy_field_cols]
                assert "track_legacy_field_id" in legacy_field_col_names
                assert "track_legacy_tag_id" not in legacy_field_col_names
                assert "field_name" in legacy_field_col_names
                assert "tag_name" not in legacy_field_col_names
        finally:
            db.dispose()
