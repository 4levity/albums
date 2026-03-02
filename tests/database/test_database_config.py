import contextlib
from pathlib import Path

import pytest

from albums.checks.all import ALL_CHECK_NAMES
from albums.checks.tags.check_album_tag import CheckAlbumTag
from albums.configuration import DEFAULT_IMPORT_PATH, DEFAULT_IMPORT_PATH_LIST, Configuration, PathCompatibilityOption, RescanOption
from albums.database import connection
from albums.database.db_config import load, save


class TestDatabaseConfig:
    def test_database_config_load_default(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            config = load(db)
            assert len(config.checks) == len(ALL_CHECK_NAMES)
            assert config.checks[CheckAlbumTag.name]["enabled"]
            assert len(config.checks[CheckAlbumTag.name]) == len(CheckAlbumTag.default_config)
            assert config.import_path_default_T == DEFAULT_IMPORT_PATH
            assert config.import_paths_T == DEFAULT_IMPORT_PATH_LIST
            assert config.library == Path(".")
            assert config.open_folder_command == ""
            assert config.path_compatibility == PathCompatibilityOption.UNIVERSAL
            assert config.rescan == RescanOption.AUTO
            assert config.tagger == ""

    def test_database_config_save_load(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            config = Configuration(
                checks={"disc-numbering": {"enabled": False, "discs_in_separate_folders": False, "disctotal_policy": "never"}},
                import_path_default_T="$album",
                import_paths_T=("various",),
                library=Path("/path/to"),
                open_folder_command="open",
                path_compatibility=PathCompatibilityOption.LINUX,
                rescan=RescanOption.NEVER,
                tagger="puddletag",
            )

            save(db, config)
            loaded = load(db)

            check = loaded.checks["disc-numbering"]
            assert not check["enabled"]
            assert check["disctotal_policy"] == "never"
            assert not check["discs_in_separate_folders"]
            assert loaded.import_path_default_T == "$album"
            assert loaded.import_paths_T == ("various",)
            assert loaded.library == Path("/path/to")
            assert loaded.open_folder_command == "open"
            assert loaded.path_compatibility == PathCompatibilityOption.LINUX
            assert loaded.rescan == RescanOption.NEVER
            assert loaded.tagger == "puddletag"

    def test_database_config_load_ignored_values(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            db.execute("INSERT INTO setting(name, value_json) VALUES('foo.bar', 'true');")
            assert len(db.execute("SELECT name FROM setting WHERE name='foo.bar';").fetchall()) == 1
            load(db)
            # ignored setting removed from db
            assert len(db.execute("SELECT name FROM setting WHERE name='foo.bar';").fetchall()) == 0

    def test_database_config_save_overwrite(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            save(db, Configuration({"cover-filename": {"enabled": True, "filename": "cover.*", "jpeg_quality": 90}}, library=Path("/path/to")))
            loaded = load(db)
            assert str(loaded.library) == "/path/to"
            assert loaded.checks["cover-filename"]["enabled"]
            assert loaded.checks["cover-filename"]["filename"] == "cover.*"
            assert loaded.checks["cover-filename"]["jpeg_quality"] == 90

            save(db, Configuration({"cover-filename": {"enabled": False, "filename": "cover.jpg", "jpeg_quality": 95}}, library=Path("/new")))
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
