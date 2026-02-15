import contextlib

import pytest

from albums.checks.all import ALL_CHECK_NAMES
from albums.checks.check_album_tag import CheckAlbumTag
from albums.config import DEFAULT_SETTINGS, CheckConfiguration, Configuration
from albums.database import connection
from albums.database.configuration import load, save


class TestDatabaseConfig:
    def test_database_config_load_default(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            config = load(db)
            assert len(config.settings) == len(DEFAULT_SETTINGS)
            assert len(config.checks) == len(ALL_CHECK_NAMES)
            assert config.checks[CheckAlbumTag.name].enabled
            assert len(config.checks[CheckAlbumTag.name].settings) == len(CheckAlbumTag.default_config) - 1  # all settings except enabled

    def test_database_config_save_load(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            config = Configuration(
                {"library": "/path/to"},
                {"disc_numbering": CheckConfiguration(False, {"discs_in_separate_folders": False, "disctotal_policy": "never"})},
            )

            save(db, config)
            loaded = load(db)

            assert loaded.settings["library"] == "/path/to"
            check = loaded.checks["disc_numbering"]
            assert not check.enabled
            assert check.settings["disctotal_policy"] == "never"
            assert not check.settings["discs_in_separate_folders"]

    def test_database_config_save_overwrite(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            save(db, Configuration({"library": "/path/to"}, {"required_tags": CheckConfiguration(True, {"tags": ["artist", "title"]})}))
            loaded = load(db)
            assert loaded.settings["library"] == "/path/to"
            assert loaded.checks["required_tags"].enabled
            assert loaded.checks["required_tags"].settings["tags"] == ["artist", "title"]

            save(db, Configuration({"library": "/new"}, {"required_tags": CheckConfiguration(False, {"tags": ["genre"]})}))
            loaded = load(db)
            assert loaded.settings["library"] == "/new"
            assert not loaded.checks["required_tags"].enabled
            assert loaded.checks["required_tags"].settings["tags"] == ["genre"]

    def test_database_config_save_invalid(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            save(db, Configuration({"library": "/new"}, {"required_tags": CheckConfiguration(False, {"tags": ["title"]})}))  # ok
            with pytest.raises(ValueError):
                save(db, Configuration({"library": "/new"}, {"required_tags": CheckConfiguration(False, {"tags": (1, 2)})}))  # type: ignore
            with pytest.raises(ValueError):
                save(db, Configuration({"INVALID": "/new"}, {"required_tags": CheckConfiguration(False, {"tags": ["title"]})}))
            with pytest.raises(ValueError):
                save(db, Configuration({"library": "/new"}, {"INVALID": CheckConfiguration(False, {"tags": ["title"]})}))  # ok
            with pytest.raises(ValueError):
                save(db, Configuration({"library": "/new"}, {"required_tags": CheckConfiguration(False, {"INVALID": ["title"]})}))
