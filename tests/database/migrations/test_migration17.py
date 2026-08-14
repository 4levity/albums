from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.database import MEMORY, db_open, migrate

from .sql_helpers import make_track_sql


class TestMigration17CheckRename:
    """Test that migration 17 renames check 'album-tag' to 'album' and single-value-fields.tags to single-value-fields.values."""

    def test_check_name_renamed_in_ignore_table(self):
        """Test that album_ignore_check entries with old check name are updated."""
        db = db_open(MEMORY, version=16)
        try:
            # Use raw SQL for track creation to avoid ORM table name mismatch
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES (:path);"), {"path": "foo/"})
                conn.execute(text(make_track_sql(1, "1.flac")))

            # Insert old check name into ignore table manually to simulate pre-migration state
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album_ignore_check (album_id, check_name) VALUES (1, 'album-tag');"))

            # Migrate v16 -> v17
            migrate(db, quiet=True, target_version=17)

            with Session(db) as session:
                ignore_rows = session.execute(text("SELECT check_name FROM album_ignore_check WHERE album_id = :aid;"), {"aid": 1}).fetchall()
                assert len(ignore_rows) == 1
                assert ignore_rows[0].check_name == "album"
        finally:
            db.dispose()

    def test_check_config_renamed_in_setting_table(self):
        """Test that setting entries with old check prefix are updated."""
        db = db_open(MEMORY, version=16)
        try:
            # Insert old check config keys into setting table manually
            with db.begin() as conn:
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('album-tag.enabled', 'false');"))
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('album-tag.ignore_folders', '[\"test\"]');"))
                # Add another unrelated check to verify it's not affected
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('cover-filename.enabled', 'true');"))

            # Migrate v16 -> v17
            migrate(db, quiet=True, target_version=17)

            with Session(db) as session:
                settings = session.execute(text("SELECT name, value_json FROM setting ORDER BY name;")).fetchall()
                setting_dict = {r.name: r.value_json for r in settings}

                # Check that old names were renamed
                assert "album.enabled" in setting_dict
                assert "album.ignore_folders" in setting_dict
                assert setting_dict["album.enabled"] == "false"

                # Check that unrelated check was not affected
                assert "cover-filename.enabled" in setting_dict

                # Check that old names don't exist anymore
                assert "album-tag.enabled" not in setting_dict
                assert "album-tag.ignore_folders" not in setting_dict
        finally:
            db.dispose()

    def test_multiple_albums_with_same_ignore(self):
        """Test that multiple albums ignoring the same old check name are all updated."""
        db = db_open(MEMORY, version=16)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT OR IGNORE INTO album (album_id, path) VALUES (1, 'album1/');"))
                conn.execute(text(make_track_sql(1, "1.flac")))
                conn.execute(text("INSERT OR IGNORE INTO album (album_id, path) VALUES (2, 'album2/');"))
                conn.execute(text(make_track_sql(2, "1.flac")))

            # Insert old check name for both albums
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album_ignore_check (album_id, check_name) VALUES (1, 'album-tag');"))
                conn.execute(text("INSERT INTO album_ignore_check (album_id, check_name) VALUES (2, 'album-tag');"))

            # Migrate v16 -> v17
            migrate(db, quiet=True, target_version=17)

            with Session(db) as session:
                ignore_rows = session.execute(text("SELECT album_id, check_name FROM album_ignore_check ORDER BY album_id;")).fetchall()
                assert len(ignore_rows) == 2
                assert all(r.check_name == "album" for r in ignore_rows)
        finally:
            db.dispose()

    def test_noop_when_no_old_check_references(self):
        """Migration should handle databases with no old check name references gracefully."""
        db = db_open(MEMORY, version=16)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES (:path);"), {"path": "foo/"})
                conn.execute(text(make_track_sql(1, "1.flac")))

            # Insert only unrelated checks and settings
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album_ignore_check (album_id, check_name) VALUES (1, 'artist');"))
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('artist.enabled', 'true');"))

            # Migrate v16 -> v17
            migrate(db, quiet=True, target_version=17)

            with Session(db) as session:
                ignore_rows = session.execute(text("SELECT check_name FROM album_ignore_check;")).fetchall()
                assert len(ignore_rows) == 1
                assert ignore_rows[0].check_name == "artist"

                setting_rows = session.execute(text("SELECT name FROM setting;")).fetchall()
                setting_names = [r.name for r in setting_rows]
                assert "artist.enabled" in setting_names
                assert not any("album-tag" in name or "album" in name for name in setting_names)
        finally:
            db.dispose()

    def test_single_setting_renamed(self):
        """Test that single-value-fields.tags setting is updated (the check is also renamed)."""
        db = db_open(MEMORY, version=16)
        try:
            # Insert old check config keys into setting table manually
            with db.begin() as conn:
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('single-value-tags.enabled', 'false');"))
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('single-value-tags.tags', '[\"test\"]');"))
                # Add another unrelated check to verify it's not affected
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('cover-filename.enabled', 'true');"))

            # Migrate v16 -> v17
            migrate(db, quiet=True, target_version=17)

            with Session(db) as session:
                settings = session.execute(text("SELECT name, value_json FROM setting ORDER BY name;")).fetchall()
                setting_dict = {r.name: r.value_json for r in settings}

                # Check that old names were renamed
                assert "single-value-fields.enabled" in setting_dict
                assert "single-value-fields.fields" in setting_dict
                assert setting_dict["single-value-fields.enabled"] == "false"

                # Check that unrelated check was not affected
                assert "cover-filename.enabled" in setting_dict

                # Check that old names don't exist anymore
                assert "single-value-tags.enabled" not in setting_dict
                assert "single-value-tags.tags" not in setting_dict
        finally:
            db.dispose()
