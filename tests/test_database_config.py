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
            save(db, Configuration({"cover-filename": {"enabled": True, "filename": "cover.*", "jpeg_quality": 90}}, Path("/path/to")))
            loaded = load(db)
            assert str(loaded.library) == "/path/to"
            assert loaded.checks["cover-filename"]["enabled"]
            assert loaded.checks["cover-filename"]["filename"] == "cover.*"
            assert loaded.checks["cover-filename"]["jpeg_quality"] == 90

            save(db, Configuration({"cover-filename": {"enabled": False, "filename": "cover.jpg", "jpeg_quality": 95}}, Path("/new")))
            loaded = load(db)
            assert str(loaded.library) == "/new"
            assert not loaded.checks["cover-filename"]["enabled"]
            assert loaded.checks["cover-filename"]["filename"] == "cover.jpg"
            assert loaded.checks["cover-filename"]["jpeg_quality"] == 95

    def test_database_config_save_invalid(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            save(db, Configuration({"cover-filename": {"enabled": True, "filename": "cover.*", "jpeg_quality": 90}}))  # ok
            with pytest.raises(ValueError):
                save(db, Configuration({"cover-filename": {"enabled": True, "filename": True, "jpeg_quality": 90}}))  # type: ignore
            with pytest.raises(ValueError):
                save(db, Configuration({"INVALID": {"enabled": True, "filename": "cover.*", "jpeg_quality": 90}}))
            with pytest.raises(ValueError):
                save(db, Configuration({"cover-filename": {"enabled": True, "INVALID": "cover.*", "jpeg_quality": 90}}))
