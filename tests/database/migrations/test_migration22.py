from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.config import config_load
from albums.database import MEMORY, db_open, migrate


class TestMigration22CheckRename:
    """Test that migration 22 renames check 'duplicate-pathname' to 'duplicate-filename'."""

    def test_check_name_renamed_in_ignore_table(self):
        """Per-album ignores of the old check name must be renamed, other ignores untouched."""
        db = db_open(MEMORY, version=21)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES (:path);"), {"path": "foo/"})
                conn.execute(text("INSERT INTO album_ignore_check (album_id, check_name) VALUES (1, 'duplicate-pathname');"))
                conn.execute(text("INSERT INTO album_ignore_check (album_id, check_name) VALUES (1, 'duplicate-folder-name');"))

            migrate(db, quiet=True, target_version=22)

            with Session(db) as session:
                rows = session.execute(text("SELECT check_name FROM album_ignore_check WHERE album_id = 1 ORDER BY check_name;")).fetchall()
                assert [row.check_name for row in rows] == ["duplicate-filename", "duplicate-folder-name"]
        finally:
            db.dispose()

    def test_check_config_renamed_in_setting_table(self):
        """Setting keys with the old check prefix must be renamed, other settings untouched."""
        db = db_open(MEMORY, version=21)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('duplicate-pathname.enabled', 'false');"))
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('settings.library', '/music');"))

            migrate(db, quiet=True, target_version=22)

            with Session(db) as session:
                settings = {row.name: row.value_json for row in session.execute(text("SELECT name, value_json FROM setting;")).fetchall()}
            assert settings == {"duplicate-filename.enabled": "false", "settings.library": "/music"}
        finally:
            db.dispose()

    def test_migrated_config_loads(self):
        """After migration the renamed setting must load into the new check config instead of being discarded as unknown."""
        db = db_open(MEMORY, version=21)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('duplicate-pathname.enabled', 'false');"))

            migrate(db, quiet=True, target_version=22)

            config = config_load(db)
            assert config.checks["duplicate-filename"]["enabled"] is False
        finally:
            db.dispose()
