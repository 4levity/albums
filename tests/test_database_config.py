import contextlib
from pathlib import Path

import pytest

from albums.checks.all import ALL_CHECK_NAMES
from albums.checks.check_album_tag import CheckAlbumTag
from albums.config import Configuration, RescanOption
from albums.database import connection
from albums.database.configuration import load, save


class TestDatabaseConfig:
    def test_database_config_load_default(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            config = load(db)
            assert config.library == Path(".")
            assert config.rescan == RescanOption.AUTO
            assert config.open_folder_command == ""
            assert config.tagger == ""
            assert len(config.checks) == len(ALL_CHECK_NAMES)
            assert config.checks[CheckAlbumTag.name]["enabled"]
            assert len(config.checks[CheckAlbumTag.name]) == len(CheckAlbumTag.default_config)

    def test_database_config_save_load(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            config = Configuration(
                {"disc_numbering": {"enabled": False, "discs_in_separate_folders": False, "disctotal_policy": "never"}}, Path("/path/to")
            )

            save(db, config)
            loaded = load(db)

            assert str(loaded.library) == "/path/to"
            check = loaded.checks["disc_numbering"]
            assert not check["enabled"]
            assert check["disctotal_policy"] == "never"
            assert not check["discs_in_separate_folders"]

    def test_database_config_save_overwrite(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            save(db, Configuration({"required_tags": {"enabled": True, "tags": ["artist", "title"]}}, Path("/path/to")))
            loaded = load(db)
            assert str(loaded.library) == "/path/to"
            assert loaded.checks["required_tags"]["enabled"]
            assert loaded.checks["required_tags"]["tags"] == ["artist", "title"]

            save(db, Configuration({"required_tags": {"enabled": False, "tags": ["genre"]}}, Path("/new")))
            loaded = load(db)
            assert str(loaded.library) == "/new"
            assert not loaded.checks["required_tags"]["enabled"]
            assert loaded.checks["required_tags"]["tags"] == ["genre"]

    def test_database_config_save_invalid(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            save(db, Configuration({"required_tags": {"enabled": True, "tags": ["title"]}}))  # ok
            with pytest.raises(ValueError):
                save(db, Configuration({"required_tags": {"enabled": True, "tags": (1, 2)}}))  # type: ignore
            with pytest.raises(ValueError):
                save(db, Configuration({"INVALID": {"enabled": True, "tags": ["title"]}}))
            with pytest.raises(ValueError):
                save(db, Configuration({"required_tags": {"enabled": True, "INVALID": ["title"]}}))
