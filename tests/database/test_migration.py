import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.database import connection, schema
from albums.types import Album, BasicTag, Track


class TestMigration16LegacyTags:
    """Test that migration 16 migrates legacy vorbis tag names to canonical BasicTag field names."""

    def test_legacy_tags_migrated(self):
        """Test basic migration of legacy tags to canonical names."""
        db = connection.open(connection.MEMORY, version=15)
        try:
            with Session(db) as session:
                album = Album(
                    path="foo" + os.sep,
                    tracks=[
                        Track(filename="1.flac", tag={BasicTag.ALBUMARTIST: "Canonical Artist"}),
                        Track(filename="2.flac", tag={BasicTag.ARTIST: "Test"}),
                    ],
                )
                session.add(album)
                session.flush()
                track1_id = album.tracks[0].track_id
                track2_id = album.tracks[1].track_id
                session.commit()

            # Insert legacy tags directly into the database to simulate pre-migration state
            with db.begin() as conn:
                # Track 1 has both canonical and legacy tags for artist
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track1_id}, 'album artist', 'LegacyArtist');"))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track1_id}, 'publisher', 'PublisherVal');"))
                # Track 2 has legacy-only tags
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track2_id}, 'label', 'LabelVal');"))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track2_id}, 'totaldiscs', '3');"))

            # Migrate v15 → v16 only
            schema.migrate(db, quiet=True, target_version=16)

            with Session(db) as session:
                # Verify legacy tags were recorded in track_legacy_tag
                legacy_tags = session.execute(text("SELECT track_id, tag_name FROM track_legacy_tag ORDER BY track_id, tag_name;")).fetchall()
                assert len(legacy_tags) == 4
                assert (track1_id, "album artist") in [(r.track_id, r.tag_name) for r in legacy_tags]
                assert (track1_id, "publisher") in [(r.track_id, r.tag_name) for r in legacy_tags]
                assert (track2_id, "label") in [(r.track_id, r.tag_name) for r in legacy_tags]
                assert (track2_id, "totaldiscs") in [(r.track_id, r.tag_name) for r in legacy_tags]

            # Verify values were migrated to canonical names
            with Session(db) as session:
                tag_rows = session.execute(text("SELECT track_id, name, value FROM track_tag ORDER BY track_id, name, value;")).fetchall()
                # Track 1 should have: canonical ALBUMARTIST + migrated legacy albumartist, and migrated publisher to organization
                track1_tags = {(r.name, r.value) for r in tag_rows if r.track_id == track1_id}
                assert (BasicTag.ALBUMARTIST.value, "Canonical Artist") in track1_tags  # original canonical
                assert (BasicTag.ALBUMARTIST.value, "LegacyArtist") in track1_tags  # migrated from "album artist"
                assert (BasicTag.ORGANIZATION.value, "PublisherVal") in track1_tags  # migrated from "publisher"

                # Track 2 should have: ARTIST (original) + migrated label to organization + migrated totaldiscs to disctotal
                track2_tags = {(r.name, r.value) for r in tag_rows if r.track_id == track2_id}
                assert (BasicTag.ARTIST.value, "Test") in track2_tags
                assert (BasicTag.ORGANIZATION.value, "LabelVal") in track2_tags  # migrated from "label"
                assert (BasicTag.DISCTOTAL.value, "3") in track2_tags  # migrated from "totaldiscs"

            # Verify old legacy tag rows were deleted
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
            with Session(db) as session:
                album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicTag.ALBUMARTIST: "SameArtist"})])
                session.add(album)
                session.flush()
                track_id = album.tracks[0].track_id
                session.commit()

            # Insert legacy tag with SAME value as canonical
            with db.begin() as conn:
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track_id}, 'album artist', 'SameArtist');"))

            schema.migrate(db, quiet=True, target_version=16)

            with Session(db) as session:
                # Should only have ONE row with the canonical name and this value (no duplicates)
                tag_rows = session.execute(text("SELECT track_id, name, value FROM track_tag WHERE track_id = :tid;"), {"tid": track_id}).fetchall()
                assert len(tag_rows) == 1
                assert tag_rows[0].name == BasicTag.ALBUMARTIST.value
                assert tag_rows[0].value == "SameArtist"

            # Verify legacy was recorded
            with Session(db) as session:
                legacy_rows = session.execute(text("SELECT tag_name FROM track_legacy_tag WHERE track_id = :tid;"), {"tid": track_id}).fetchall()
                assert len(legacy_rows) == 1
                assert legacy_rows[0].tag_name == "album artist"
        finally:
            db.dispose()

    def test_noop_when_no_legacy_tags(self):
        """Migration should be a no-op when there are no legacy tags."""
        db = connection.open(connection.MEMORY, version=15)
        try:
            with Session(db) as session:
                album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicTag.ALBUMARTIST: "Artist"})])
                session.add(album)
                session.flush()
                session.commit()

            schema.migrate(db, quiet=True, target_version=16)

            with Session(db) as session:
                # Should be unchanged
                tag_rows = session.execute(text("SELECT name, value FROM track_tag;")).fetchall()
                assert len(tag_rows) == 1
                assert tag_rows[0].name == BasicTag.ALBUMARTIST.value
                assert tag_rows[0].value == "Artist"

                # No legacy tags recorded
                legacy_count = session.scalar(text("SELECT COUNT(*) FROM track_legacy_tag;"))
                assert legacy_count == 0
        finally:
            db.dispose()

    def test_both_label_and_publisher_migrate_to_organization(self):
        """Verify both 'label' and 'publisher' legacy tags migrate to ORGANIZATION without creating duplicates."""
        db = connection.open(connection.MEMORY, version=15)
        try:
            with Session(db) as session:
                album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicTag.ORGANIZATION: "Existing"})])
                session.add(album)
                session.flush()
                track_id = album.tracks[0].track_id
                session.commit()

            # Insert both legacy tags
            with db.begin() as conn:
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track_id}, 'label', 'LabelCo');"))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track_id}, 'publisher', 'PublishCo');"))

            schema.migrate(db, quiet=True, target_version=16)

            with Session(db) as session:
                tag_rows = session.execute(
                    text("SELECT name, value FROM track_tag WHERE track_id = :tid ORDER BY value;"), {"tid": track_id}
                ).fetchall()
                # Should have 3 rows: Existing + LabelCo + PublishCo all under ORGANIZATION
                assert len(tag_rows) == 3
                for row in tag_rows:
                    assert row.name == BasicTag.ORGANIZATION.value

            with Session(db) as session:
                # Both legacy tag names should be recorded
                legacy_rows = session.execute(
                    text("SELECT tag_name FROM track_legacy_tag WHERE track_id = :tid ORDER BY tag_name;"), {"tid": track_id}
                ).fetchall()
                assert len(legacy_rows) == 2
                assert legacy_rows[0].tag_name in ("label", "publisher")
                assert legacy_rows[1].tag_name in ("label", "publisher")
        finally:
            db.dispose()
