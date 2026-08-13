from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.database import connection
from albums.database.migrations import migrate
from albums.tagger import BasicField

from .sql_helpers import make_track_sql


class TestMigration16LegacyTags:
    """Test that migration 16 migrates legacy vorbis field names to canonical BasicField field names."""

    def test_legacy_fields_migrated(self):
        """Test basic migration of legacy fields to canonical names."""
        db = connection.open(connection.MEMORY, version=15)
        try:
            with db.begin() as conn:
                # Use raw SQL instead of ORM - avoids track_field vs track_tag name mismatch at old schema versions
                conn.execute(text("INSERT INTO album (path) VALUES (:path);"), {"path": "foo/"})
                conn.execute(text(make_track_sql(1, "1.flac")))
                conn.execute(text(make_track_sql(1, "2.flac")))
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
            migrate(db, quiet=True, target_version=16)

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
                conn.execute(text(make_track_sql(1, "1.flac")))
                # Insert canonical field
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ALBUMARTIST.value}', 'SameArtist');"))

            # Insert legacy tag with SAME value as canonical
            with db.begin() as conn:
                conn.execute(text("INSERT INTO track_tag (track_id, name, value) VALUES (1, 'album artist', 'SameArtist');"))

            migrate(db, quiet=True, target_version=16)

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
                conn.execute(text(make_track_sql(1, "1.flac")))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ALBUMARTIST.value}', 'Artist');"))

            migrate(db, quiet=True, target_version=16)

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
                conn.execute(text(make_track_sql(1, "1.flac")))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES (1, '{BasicField.ORGANIZATION.value}', 'Existing');"))

            # Insert both legacy tags
            with db.begin() as conn:
                conn.execute(text("INSERT INTO track_tag (track_id, name, value) VALUES (1, 'label', 'LabelCo');"))
                conn.execute(text("INSERT INTO track_tag (track_id, name, value) VALUES (1, 'publisher', 'PublishCo');"))

            migrate(db, quiet=True, target_version=16)

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
