import contextlib
from pathlib import Path

import pytest

from albums.checks.all import ALL_CHECK_NAMES
from albums.checks.tags.check_album_tag import CheckAlbumTag
from albums.database import connection
from albums.database.configuration import load, save
from albums.types import Configuration, RescanOption


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
                {"disc-numbering": {"enabled": False, "discs_in_separate_folders": False, "disctotal_policy": "never"}}, Path("/path/to")
            )

            save(db, config)
            loaded = load(db)

            assert str(loaded.library) == "/path/to"
            check = loaded.checks["disc-numbering"]
            assert not check["enabled"]
            assert check["disctotal_policy"] == "never"
            assert not check["discs_in_separate_folders"]

    def test_database_config_load_ignored_values(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            db.execute("INSERT INTO setting(name, value_json) VALUES('foo.bar', 'true');")
            assert len(db.execute("SELECT name FROM setting WHERE name='foo.bar';").fetchall()) == 1
            load(db)
            # ignored setting removed from db
            assert len(db.execute("SELECT name FROM setting WHERE name='foo.bar';").fetchall()) == 0

    def test_database_config_save_overwrite(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            save(db, Configuration({"required-tags": {"enabled": True, "tags": ["artist", "title"]}}, Path("/path/to")))
            loaded = load(db)
            assert str(loaded.library) == "/path/to"
            assert loaded.checks["required-tags"]["enabled"]
            assert loaded.checks["required-tags"]["tags"] == ["artist", "title"]

            save(db, Configuration({"required-tags": {"enabled": False, "tags": ["genre"]}}, Path("/new")))
            loaded = load(db)
            assert str(loaded.library) == "/new"
            assert not loaded.checks["required-tags"]["enabled"]
            assert loaded.checks["required-tags"]["tags"] == ["genre"]

    def test_database_config_save_invalid(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            save(db, Configuration({"required-tags": {"enabled": True, "tags": ["title"]}}))  # ok
            with pytest.raises(ValueError):
                save(db, Configuration({"required-tags": {"enabled": True, "tags": (1, 2)}}))  # type: ignore
            with pytest.raises(ValueError):
                save(db, Configuration({"INVALID": {"enabled": True, "tags": ["title"]}}))
            with pytest.raises(ValueError):
                save(db, Configuration({"required-tags": {"enabled": True, "INVALID": ["title"]}}))
