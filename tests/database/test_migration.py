from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.database import connection, schema
from albums.tagger.types import BasicField


def _make_track_sql(album_id: int = 1, filename: str = "1.flac") -> str:
    """Generate SQL to insert a track row."""
    return (
        f"INSERT INTO track (album_id, filename, file_size, modify_timestamp, stream_bitrate, "
        f"stream_channels, stream_codec, stream_length, stream_sample_rate, stream_error, stream_bits_per_sample) "
        f"VALUES ({album_id}, '{filename}', 0, 0, 0, 0, '', 0, 0, '', 0);"
    )


class TestMigration16LegacyTags:
    """Test that migration 16 migrates legacy vorbis field names to canonical BasicField field names."""

    def test_legacy_fields_migrated(self):
        """Test basic migration of legacy fields to canonical names."""
        db = connection.open(connection.MEMORY, version=15)
        try:
            with db.begin() as conn:
                # Use raw SQL instead of ORM - avoids track_field vs track_tag name mismatch at old schema versions
                conn.execute(text("INSERT INTO album (path) VALUES (:path);"), {"path": "foo/"})
                conn.execute(text(_make_track_sql(1, "1.flac")))
                conn.execute(text(_make_track_sql(1, "2.flac")))
                # Insert canonical fields using lowercase names as stored in DB
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ALBUMARTIST.value}', 'Canonical Artist');"))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (2, '{BasicField.ARTIST.value}', 'Test');"))

            # Insert legacy fields directly into the database to simulate pre-migration state
            with db.begin() as conn:
                # Track 1 has both canonical and legacy fields for artist
                conn.execute(text("INSERT INTO track_tag (track_id, name, value) VALUES (1, 'album artist', 'LegacyArtist');"))
                conn.execute(text("INSERT INTO track_tag (track_id, name, value) VALUES (1, 'publisher', 'PublisherVal');"))
                # Track 2 has legacy-only fields
                conn.execute(text("INSERT INTO track_tag (track_id, name, value) VALUES (2, 'label', 'LabelVal');"))
                conn.execute(text("INSERT INTO track_tag (track_id, name, value) VALUES (2, 'totaldiscs', '3');"))

            # Migrate v15 → v16 only
            schema.migrate(db, quiet=True, target_version=16)

            with Session(db) as session:
                # Verify legacy fields were recorded in track_legacy_tag
                legacy_fields = session.execute(text("SELECT track_id, tag_name FROM track_legacy_tag ORDER BY track_id, tag_name;")).fetchall()
                assert len(legacy_fields) == 4
                assert (1, "album artist") in [(r.track_id, r.tag_name) for r in legacy_fields]
                assert (1, "publisher") in [(r.track_id, r.tag_name) for r in legacy_fields]
                assert (2, "label") in [(r.track_id, r.tag_name) for r in legacy_fields]
                assert (2, "totaldiscs") in [(r.track_id, r.tag_name) for r in legacy_fields]

            # Verify values were migrated to canonical names
            with Session(db) as session:
                tag_rows = session.execute(text("SELECT track_id, name, value FROM track_tag ORDER BY track_id, name, value;")).fetchall()
                # Track 1 should have: canonical ALBUMARTIST + migrated legacy albumartist, and migrated publisher to organization
                track1_tags = {(r.name, r.value) for r in tag_rows if r.track_id == 1}
                assert (BasicField.ALBUMARTIST.value, "Canonical Artist") in track1_tags  # original canonical
                assert (BasicField.ALBUMARTIST.value, "LegacyArtist") in track1_tags  # migrated from "album artist"
                assert (BasicField.ORGANIZATION.value, "PublisherVal") in track1_tags  # migrated from "publisher"

                # Track 2 should have: ARTIST (original) + migrated label to organization + migrated totaldiscs to disctotal
                track2_tags = {(r.name, r.value) for r in tag_rows if r.track_id == 2}
                assert (BasicField.ARTIST.value, "Test") in track2_tags
                assert (BasicField.ORGANIZATION.value, "LabelVal") in track2_tags  # migrated from "label"
                assert (BasicField.DISCTOTAL.value, "3") in track2_tags  # migrated from "totaldiscs"

            # Verify old legacy fields rows were deleted
            with Session(db) as session:
                legacy_rows = session.execute(
                    text("SELECT name FROM track_tag WHERE name IN ('album artist', 'label', 'publisher', 'totaldiscs');")
                ).fetchall()
                assert len(legacy_rows) == 0
        finally:
            db.dispose()

    def test_duplicate_values_not_created(self):
        """Verify migration doesn't create duplicate values when legacy and canonical have same value."""
        db = connection.open(connection.MEMORY, version=15)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES (:path);"), {"path": "foo/"})
                conn.execute(text(_make_track_sql(1, "1.flac")))
                # Insert canonical field
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ALBUMARTIST.value}', 'SameArtist');"))

            # Insert legacy tag with SAME value as canonical
            with db.begin() as conn:
                conn.execute(text("INSERT INTO track_tag (track_id, name, value) VALUES (1, 'album artist', 'SameArtist');"))

            schema.migrate(db, quiet=True, target_version=16)

            with Session(db) as session:
                # Should only have ONE row with the canonical name and this value (no duplicates)
                tag_rows = session.execute(text("SELECT track_id, name, value FROM track_tag WHERE track_id = :tid;"), {"tid": 1}).fetchall()
                assert len(tag_rows) == 1
                assert tag_rows[0].name == BasicField.ALBUMARTIST.value
                assert tag_rows[0].value == "SameArtist"

            # Verify legacy was recorded
            with Session(db) as session:
                legacy_rows = session.execute(text("SELECT tag_name FROM track_legacy_tag WHERE track_id = :tid;"), {"tid": 1}).fetchall()
                assert len(legacy_rows) == 1
                assert legacy_rows[0].tag_name == "album artist"
        finally:
            db.dispose()

    def test_noop_when_no_legacy_fields(self):
        """Migration should be a no-op when there are no legacy fields."""
        db = connection.open(connection.MEMORY, version=15)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES (:path);"), {"path": "foo/"})
                conn.execute(text(_make_track_sql(1, "1.flac")))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ALBUMARTIST.value}', 'Artist');"))

            schema.migrate(db, quiet=True, target_version=16)

            with Session(db) as session:
                # Should be unchanged
                tag_rows = session.execute(text("SELECT name, value FROM track_tag;")).fetchall()
                assert len(tag_rows) == 1
                assert tag_rows[0].name == BasicField.ALBUMARTIST.value
                assert tag_rows[0].value == "Artist"

                # No legacy fields recorded
                legacy_count = session.scalar(text("SELECT COUNT(*) FROM track_legacy_tag;"))
                assert legacy_count == 0
        finally:
            db.dispose()

    def test_both_label_and_publisher_migrate_to_organization(self):
        """Verify both 'label' and 'publisher' legacy fields migrate to ORGANIZATION without creating duplicates."""
        db = connection.open(connection.MEMORY, version=15)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES (:path);"), {"path": "foo/"})
                conn.execute(text(_make_track_sql(1, "1.flac")))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ORGANIZATION.value}', 'Existing');"))

            # Insert both legacy tags
            with db.begin() as conn:
                conn.execute(text("INSERT INTO track_tag (track_id, name, value) VALUES (1, 'label', 'LabelCo');"))
                conn.execute(text("INSERT INTO track_tag (track_id, name, value) VALUES (1, 'publisher', 'PublishCo');"))

            schema.migrate(db, quiet=True, target_version=16)

            with Session(db) as session:
                tag_rows = session.execute(text("SELECT name, value FROM track_tag WHERE track_id = :tid ORDER BY value;"), {"tid": 1}).fetchall()
                # Should have 3 rows: Existing + LabelCo + PublishCo all under ORGANIZATION
                assert len(tag_rows) == 3
                for row in tag_rows:
                    assert row.name == BasicField.ORGANIZATION.value

            with Session(db) as session:
                # Both legacy tag names should be recorded
                legacy_rows = session.execute(
                    text("SELECT tag_name FROM track_legacy_tag WHERE track_id = :tid ORDER BY tag_name;"), {"tid": 1}
                ).fetchall()
                assert len(legacy_rows) == 2
                assert legacy_rows[0].tag_name in ("label", "publisher")
                assert legacy_rows[1].tag_name in ("label", "publisher")
        finally:
            db.dispose()


class TestMigration17CheckRename:
    """Test that migration 17 renames check 'album-tag' to 'album' and single-value-fields.tags to single-value-fields.values."""

    def test_check_name_renamed_in_ignore_table(self):
        """Test that album_ignore_check entries with old check name are updated."""
        db = connection.open(connection.MEMORY, version=16)
        try:
            # Use raw SQL for track creation to avoid ORM table name mismatch
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES (:path);"), {"path": "foo/"})
                conn.execute(text(_make_track_sql(1, "1.flac")))

            # Insert old check name into ignore table manually to simulate pre-migration state
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album_ignore_check (album_id, check_name) VALUES (1, 'album-tag');"))

            # Migrate v16 -> v17
            schema.migrate(db, quiet=True, target_version=17)

            with Session(db) as session:
                ignore_rows = session.execute(text("SELECT check_name FROM album_ignore_check WHERE album_id = :aid;"), {"aid": 1}).fetchall()
                assert len(ignore_rows) == 1
                assert ignore_rows[0].check_name == "album"
        finally:
            db.dispose()

    def test_check_config_renamed_in_setting_table(self):
        """Test that setting entries with old check prefix are updated."""
        db = connection.open(connection.MEMORY, version=16)
        try:
            # Insert old check config keys into setting table manually
            with db.begin() as conn:
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('album-tag.enabled', 'false');"))
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('album-tag.ignore_folders', '[\"test\"]');"))
                # Add another unrelated check to verify it's not affected
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('cover-filename.enabled', 'true');"))

            # Migrate v16 -> v17
            schema.migrate(db, quiet=True, target_version=17)

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
        db = connection.open(connection.MEMORY, version=16)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT OR IGNORE INTO album (album_id, path) VALUES (1, 'album1/');"))
                conn.execute(text(_make_track_sql(1, "1.flac")))
                conn.execute(text("INSERT OR IGNORE INTO album (album_id, path) VALUES (2, 'album2/');"))
                conn.execute(text(_make_track_sql(2, "1.flac")))

            # Insert old check name for both albums
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album_ignore_check (album_id, check_name) VALUES (1, 'album-tag');"))
                conn.execute(text("INSERT INTO album_ignore_check (album_id, check_name) VALUES (2, 'album-tag');"))

            # Migrate v16 -> v17
            schema.migrate(db, quiet=True, target_version=17)

            with Session(db) as session:
                ignore_rows = session.execute(text("SELECT album_id, check_name FROM album_ignore_check ORDER BY album_id;")).fetchall()
                assert len(ignore_rows) == 2
                assert all(r.check_name == "album" for r in ignore_rows)
        finally:
            db.dispose()

    def test_noop_when_no_old_check_references(self):
        """Migration should handle databases with no old check name references gracefully."""
        db = connection.open(connection.MEMORY, version=16)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES (:path);"), {"path": "foo/"})
                conn.execute(text(_make_track_sql(1, "1.flac")))

            # Insert only unrelated checks and settings
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album_ignore_check (album_id, check_name) VALUES (1, 'artist');"))
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('artist.enabled', 'true');"))

            # Migrate v16 -> v17
            schema.migrate(db, quiet=True, target_version=17)

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
        db = connection.open(connection.MEMORY, version=16)
        try:
            # Insert old check config keys into setting table manually
            with db.begin() as conn:
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('single-value-tags.enabled', 'false');"))
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('single-value-tags.tags', '[\"test\"]');"))
                # Add another unrelated check to verify it's not affected
                conn.execute(text("INSERT INTO setting (name, value_json) VALUES ('cover-filename.enabled', 'true');"))

            # Migrate v16 -> v17
            schema.migrate(db, quiet=True, target_version=17)

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


class TestMigration18TableNameRenamed:
    """Test that migration 18 renames track_tag to track_field and related objects."""

    def test_track_tag_renamed_to_track_field(self):
        """Test that track_tag table is renamed to track_field with data preserved."""
        db = connection.open(connection.MEMORY, version=17)
        try:
            # Insert rows into old track_tag table using raw SQL
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES ('test_album');"))
                conn.execute(text(_make_track_sql(1, "1.flac")))
                # track_tag rows (old name) - use lowercase field names as stored in DB
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ARTIST.value}', 'TestArtist');"))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ALBUM.value}', 'TestAlbum');"))

            # Migrate v17 -> v18
            schema.migrate(db, quiet=True, target_version=18)

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
        db = connection.open(connection.MEMORY, version=17)
        try:
            # Insert a minimal album + track
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES ('test_album');"))
                conn.execute(text(_make_track_sql(1, "1.flac")))
                # track_legacy_tag row with old column name (tag_name)
                conn.execute(text("INSERT INTO track_legacy_tag (track_id, tag_name) VALUES (1, 'legacy_vorbis_comment');"))

            # Migrate v17 -> v18
            schema.migrate(db, quiet=True, target_version=18)

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
        db = connection.open(connection.MEMORY, version=17)
        try:
            # Insert data to make sure tables/indexes have rows
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES ('test_album');"))
                conn.execute(text(_make_track_sql(1, "1.flac")))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ARTIST.value}', 'A');"))
                conn.execute(text("INSERT INTO track_legacy_tag (track_id, tag_name) VALUES (1, 'old_field');"))

            # Migrate v17 -> v18
            schema.migrate(db, quiet=True, target_version=18)

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
        db = connection.open(connection.MEMORY, version=17)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES ('test_album');"))
                conn.execute(text(_make_track_sql(1, "1.flac")))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ARTIST.value}', 'A');"))
                conn.execute(text("INSERT INTO track_legacy_tag (track_id, tag_name) VALUES (1, 'old_field');"))

            schema.migrate(db, quiet=True, target_version=18)

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
