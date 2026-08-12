import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.database import connection, schema
from albums.entities import Album, Track
from albums.tagger.types import BasicField


class TestMigration16LegacyTags:
    """Test that migration 16 migrates legacy vorbis field names to canonical BasicField field names."""

    def test_legacy_tags_migrated(self):
        """Test basic migration of legacy fields to canonical names."""
        db = connection.open(connection.MEMORY, version=15)
        try:
            with Session(db) as session:
                album = Album(
                    path="foo" + os.sep,
                    tracks=[
                        Track(filename="1.flac", tag={BasicField.ALBUMARTIST: "Canonical Artist"}),
                        Track(filename="2.flac", tag={BasicField.ARTIST: "Test"}),
                    ],
                )
                session.add(album)
                session.flush()
                track1_id = album.tracks[0].track_id
                track2_id = album.tracks[1].track_id
                session.commit()

            # Insert legacy fields directly into the database to simulate pre-migration state
            with db.begin() as conn:
                # Track 1 has both canonical and legacy fields for artist
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track1_id}, 'album artist', 'LegacyArtist');"))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track1_id}, 'publisher', 'PublisherVal');"))
                # Track 2 has legacy-only fields
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track2_id}, 'label', 'LabelVal');"))
                conn.execute(text(f"INSERT INTO track_tag (track_id, name, value) VALUES ({track2_id}, 'totaldiscs', '3');"))

            # Migrate v15 → v16 only
            schema.migrate(db, quiet=True, target_version=16)

            with Session(db) as session:
                # Verify legacy fields were recorded in track_legacy_tag
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
                assert (BasicField.ALBUMARTIST.value, "Canonical Artist") in track1_tags  # original canonical
                assert (BasicField.ALBUMARTIST.value, "LegacyArtist") in track1_tags  # migrated from "album artist"
                assert (BasicField.ORGANIZATION.value, "PublisherVal") in track1_tags  # migrated from "publisher"

                # Track 2 should have: ARTIST (original) + migrated label to organization + migrated totaldiscs to disctotal
                track2_tags = {(r.name, r.value) for r in tag_rows if r.track_id == track2_id}
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
            with Session(db) as session:
                album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUMARTIST: "SameArtist"})])
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
                assert tag_rows[0].name == BasicField.ALBUMARTIST.value
                assert tag_rows[0].value == "SameArtist"

            # Verify legacy was recorded
            with Session(db) as session:
                legacy_rows = session.execute(text("SELECT tag_name FROM track_legacy_tag WHERE track_id = :tid;"), {"tid": track_id}).fetchall()
                assert len(legacy_rows) == 1
                assert legacy_rows[0].tag_name == "album artist"
        finally:
            db.dispose()

    def test_noop_when_no_legacy_tags(self):
        """Migration should be a no-op when there are no legacy fields."""
        db = connection.open(connection.MEMORY, version=15)
        try:
            with Session(db) as session:
                album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUMARTIST: "Artist"})])
                session.add(album)
                session.flush()
                session.commit()

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
            with Session(db) as session:
                album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ORGANIZATION: "Existing"})])
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
                    assert row.name == BasicField.ORGANIZATION.value

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


class TestMigration17CheckRename:
    """Test that migration 17 renames check 'album-tag' to 'album' and single-value-fields.tags to single-value-fields.values."""

    def test_check_name_renamed_in_ignore_table(self):
        """Test that album_ignore_check entries with old check name are updated."""
        db = connection.open(connection.MEMORY, version=16)
        try:
            with Session(db) as session:
                album = Album(
                    path="foo" + os.sep,
                    tracks=[Track(filename="1.flac")],
                )
                session.add(album)
                session.flush()
                album_id = album.album_id
                session.commit()

            # Insert old check name into ignore table manually to simulate pre-migration state
            with db.begin() as conn:
                conn.execute(text(f"INSERT INTO album_ignore_check (album_id, check_name) VALUES ({album_id}, 'album-tag');"))

            # Migrate v16 -> v17
            schema.migrate(db, quiet=True, target_version=17)

            with Session(db) as session:
                ignore_rows = session.execute(text("SELECT check_name FROM album_ignore_check WHERE album_id = :aid;"), {"aid": album_id}).fetchall()
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
            with Session(db) as session:
                album1 = Album(path="album1" + os.sep, tracks=[Track(filename="1.flac")])
                album2 = Album(path="album2" + os.sep, tracks=[Track(filename="1.flac")])
                session.add(album1)
                session.add(album2)
                session.flush()
                album1_id = album1.album_id
                album2_id = album2.album_id
                session.commit()

            # Insert old check name for both albums
            with db.begin() as conn:
                conn.execute(text(f"INSERT INTO album_ignore_check (album_id, check_name) VALUES ({album1_id}, 'album-tag');"))
                conn.execute(text(f"INSERT INTO album_ignore_check (album_id, check_name) VALUES ({album2_id}, 'album-tag');"))

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
            with Session(db) as session:
                album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
                session.add(album)
                session.flush()
                album_id = album.album_id
                session.commit()

            # Insert only unrelated checks and settings
            with db.begin() as conn:
                conn.execute(text(f"INSERT INTO album_ignore_check (album_id, check_name) VALUES ({album_id}, 'artist');"))
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
