"""Tests for Configuration.from_values() config loading and validation."""

from sqlalchemy.orm import Session

from albums.config import (
    DEFAULT_IMPORT_SCAN_MAX_PATHS,
    DEFAULT_MORE_IMPORT_PATHS,
    Configuration,
    SettingEntity,
    _migrate_legacy_convert_profile,
    config_load,
    convert_bitrate_label,
)
from albums.database import MEMORY, db_open


class TestFromValues:
    """Tests for Configuration.from_values() validation and warning behavior."""

    def test_list_with_non_string_items_warns_and_keeps_default(self, caplog):
        """List values containing non-string items trigger a warning and keep the default."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("album.ignore_folders", ["misc", 3])])  # pyright: ignore[reportArgumentType]
        assert changed is True
        assert config.checks["album"]["ignore_folders"] == ["misc"]
        assert any("album.ignore_folders" in record.message and "list items must all be strings" in record.message for record in caplog.records)

    def test_valid_list_accepted(self, caplog):
        """A list of all strings is accepted as-is."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("album.ignore_folders", ["misc", "extra"])])
        assert changed is False
        assert config.checks["album"]["ignore_folders"] == ["misc", "extra"]

    def test_non_list_for_list_default_warns(self, caplog):
        """A non-list value for a list-typed config key triggers the type-mismatch warning."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("album.ignore_folders", "misc")])
        assert changed is True
        # Type mismatch branch: default is kept
        assert config.checks["album"]["ignore_folders"] == ["misc"]

    def test_unknown_key_warns(self, caplog):
        """Unknown configuration keys trigger a warning."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("album.nonsense", 1)])
        assert changed is True
        assert any("unknown configuration item" in record.message for record in caplog.records)

    def test_unknown_section_warns(self, caplog):
        """Unknown section names trigger a warning."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("nonsense.option", 1)])
        assert changed is True
        assert any("unknown configuration item" in record.message for record in caplog.records)

    def test_key_without_section_warns(self, caplog):
        """Keys without a dotted section trigger a warning and are ignored."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("nonsense", 1)])
        assert changed is True
        assert any("expected section.name" in record.message for record in caplog.records)

    def test_more_import_paths_not_string_list_warns(self, caplog):
        """A non-list value for more_import_paths triggers a warning and keeps the default."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("settings.more_import_paths", "not-a-list")])
        assert changed is True
        assert config.more_import_paths == DEFAULT_MORE_IMPORT_PATHS
        assert any("not a list of strings" in record.message for record in caplog.records)

    def test_import_scan_max_paths_not_number_warns(self, caplog):
        """A non-numeric import_scan_max_paths triggers a warning and keeps the default."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("settings.import_scan_max_paths", "abc")])
        assert changed is True
        assert config.import_scan_max_paths == DEFAULT_IMPORT_SCAN_MAX_PATHS
        assert any("not a number" in record.message for record in caplog.records)

    def test_sync_destinations_not_dict_list_warns(self, caplog):
        """A non-list value for sync_destinations triggers a warning and keeps the default."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("settings.sync_destinations", "not-a-list")])
        assert changed is True
        assert config.sync_destinations == []
        assert any("not a list of sync destination dictionaries" in record.message for record in caplog.records)

    def test_unknown_settings_item_warns(self, caplog):
        """Unknown settings items trigger a warning."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("settings.nonsense", 1)])
        assert changed is True
        assert any("unknown configuration item" in record.message for record in caplog.records)


class TestConfigLoad:
    def test_config_load_saves_repaired_config(self):
        """config_load re-saves the repaired config after ignoring an invalid stored value."""
        db = db_open(MEMORY)
        with Session(db) as session:
            session.add(SettingEntity(name="settings.import_scan_max_paths", value="abc"))
            session.commit()
        config = config_load(db)
        assert config.import_scan_max_paths == DEFAULT_IMPORT_SCAN_MAX_PATHS
        with Session(db) as session:
            assert session.get(SettingEntity, "settings.import_scan_max_paths").value == DEFAULT_IMPORT_SCAN_MAX_PATHS


class TestConvertBitrateLabel:
    def test_flac_is_variable_lossless(self):
        assert convert_bitrate_label("flac", "") == "variable (lossless)"

    def test_empty_bitrate_is_variable_lossless(self):
        assert convert_bitrate_label("mp3", "") == "variable (lossless)"

    def test_vbr_and_cbr_labels(self):
        assert convert_bitrate_label("mp3", "vbr") == "vbr (~192 kbps)"
        assert convert_bitrate_label("m4a", "192") == "192 kbps"


class TestMigrateLegacyConvertProfile:
    def test_empty_profile_returns_none(self):
        assert _migrate_legacy_convert_profile("") is None

    def test_bitrate_option_without_value_returns_none(self):
        assert _migrate_legacy_convert_profile("-b:a mp3") is None

    def test_conflicting_bitrates_return_none(self):
        assert _migrate_legacy_convert_profile("-b:a 128k -b:a 192k mp3") is None


class TestSyncDestinationMigration:
    """Tests for migrating legacy convert_profile sync destinations to convert_file_type/convert_bitrate."""

    @staticmethod
    def _legacy_destination(profile: str) -> dict:
        return {"collection": "test", "path_root": "/music", "convert_profile": profile}

    def test_legacy_profile_maps_cleanly(self, caplog):
        """A legacy profile of supported type and bitrate maps to the new options and re-saves."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("settings.sync_destinations", [self._legacy_destination("-b:a 320k mp3")])])
        dest = config.sync_destinations[0]
        assert changed is True
        assert dest.convert_file_type == "mp3"
        assert dest.convert_bitrate == "320"
        messages = "\n".join(record.message for record in caplog.records)
        assert "-b:a 320k mp3' converted to file type 'mp3', bitrate '320 kbps'" in messages
        assert "transcoder cache is invalidated" in messages

    def test_legacy_bare_file_type_maps_to_default_bitrate(self):
        """A legacy profile with no options keeps the file type and gets the default bitrate."""
        config, changed = Configuration.from_values([("settings.sync_destinations", [self._legacy_destination("mp3")])])
        dest = config.sync_destinations[0]
        assert changed is True
        assert dest.convert_file_type == "mp3"
        assert dest.convert_bitrate == "vbr"

    def test_legacy_mp4_maps_to_m4a(self):
        config, changed = Configuration.from_values([("settings.sync_destinations", [self._legacy_destination("-b:a 192k mp4")])])
        dest = config.sync_destinations[0]
        assert changed is True
        assert dest.convert_file_type == "m4a"
        assert dest.convert_bitrate == "192"

    def test_unsupported_options_fall_back_to_defaults(self, caplog):
        """A legacy profile with options that do not map (vbr quality, sample rate) uses defaults."""
        caplog.set_level("WARNING")
        for profile in ("-q:a 4 mp3", "-b:a 192k -ar 44100 mp3", "-b:a 112k mp3", "-b:a 128k mp3 -b:a 192k mp3"):
            config, changed = Configuration.from_values([("settings.sync_destinations", [self._legacy_destination(profile)])])
            dest = config.sync_destinations[0]
            assert changed is True
            assert (dest.convert_file_type, dest.convert_bitrate) == ("mp3", "vbr"), profile
        assert any("cannot be migrated" in record.message for record in caplog.records)

    def test_unsupported_file_type_falls_back_to_defaults(self, caplog):
        """A legacy profile for an unsupported output type (ogg) uses defaults."""
        caplog.set_level("WARNING")
        config, changed = Configuration.from_values([("settings.sync_destinations", [self._legacy_destination("ogg")])])
        dest = config.sync_destinations[0]
        assert changed is True
        assert (dest.convert_file_type, dest.convert_bitrate) == ("mp3", "vbr")
        assert any("cannot be migrated" in record.message for record in caplog.records)

    def test_m4a_never_migrates_to_vbr(self):
        """Legacy m4a profiles only map to CBR bitrates (m4a has no vbr option)."""
        config, changed = Configuration.from_values([("settings.sync_destinations", [self._legacy_destination("-b:a 320k m4a")])])
        dest = config.sync_destinations[0]
        assert changed is True
        assert (dest.convert_file_type, dest.convert_bitrate) == ("m4a", "320")

    def test_new_format_destinations_not_migrated(self):
        """Destinations saved in the new format load as-is without a migrated flag."""
        config, changed = Configuration.from_values(
            [("settings.sync_destinations", [{"collection": "test", "path_root": "/music", "convert_file_type": "m4a", "convert_bitrate": "256"}])]
        )
        dest = config.sync_destinations[0]
        assert changed is False
        assert (dest.convert_file_type, dest.convert_bitrate) == ("m4a", "256")
