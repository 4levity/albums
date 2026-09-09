"""Tests for Configuration.from_values() config loading and validation."""

from albums.config import Configuration


class TestFromValues:
    """Tests for Configuration.from_values() validation and warning behavior."""

    def test_list_with_non_string_items_warns_and_keeps_default(self, caplog):
        """List values containing non-string items trigger a warning and keep the default."""
        caplog.set_level("WARNING")
        config, ignored = Configuration.from_values([("album.ignore_folders", ["misc", 3])])  # pyright: ignore[reportArgumentType]
        assert ignored is True
        assert config.checks["album"]["ignore_folders"] == ["misc"]
        assert any("album.ignore_folders" in record.message and "list items must all be strings" in record.message for record in caplog.records)

    def test_valid_list_accepted(self, caplog):
        """A list of all strings is accepted as-is."""
        caplog.set_level("WARNING")
        config, ignored = Configuration.from_values([("album.ignore_folders", ["misc", "extra"])])
        assert ignored is False
        assert config.checks["album"]["ignore_folders"] == ["misc", "extra"]

    def test_non_list_for_list_default_warns(self, caplog):
        """A non-list value for a list-typed config key triggers the type-mismatch warning."""
        caplog.set_level("WARNING")
        config, ignored = Configuration.from_values([("album.ignore_folders", "misc")])
        assert ignored is True
        # Type mismatch branch: default is kept
        assert config.checks["album"]["ignore_folders"] == ["misc"]

    def test_unknown_key_warns(self, caplog):
        """Unknown configuration keys trigger a warning."""
        caplog.set_level("WARNING")
        config, ignored = Configuration.from_values([("album.nonsense", 1)])
        assert ignored is True
        assert any("unknown configuration item" in record.message for record in caplog.records)

    def test_unknown_section_warns(self, caplog):
        """Unknown section names trigger a warning."""
        caplog.set_level("WARNING")
        config, ignored = Configuration.from_values([("nonsense.option", 1)])
        assert ignored is True
        assert any("unknown configuration item" in record.message for record in caplog.records)
