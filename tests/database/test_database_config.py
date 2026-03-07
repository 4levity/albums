from pathlib import Path
from string import Template

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from albums.checks.all import ALL_CHECK_NAMES
from albums.checks.tags.check_album_tag import CheckAlbumTag
from albums.configuration import (
    DEFAULT_IMPORT_PATH,
    DEFAULT_IMPORT_PATH_VARIOUS,
    DEFAULT_MORE_IMPORT_PATHS,
    Configuration,
    PathCompatibilityOption,
    RescanOption,
)
from albums.database import connection
from albums.database.db_config import load, save
from albums.database.models import SettingEntity


class TestDatabaseConfig:
    def test_database_config_load_default(self):
        db = connection.open(connection.MEMORY)
        try:
            config = load(db)
            assert len(config.checks) == len(ALL_CHECK_NAMES)
            assert config.checks[CheckAlbumTag.name]["enabled"]
            assert len(config.checks[CheckAlbumTag.name]) == len(CheckAlbumTag.default_config)
            assert config.default_import_path == DEFAULT_IMPORT_PATH
            assert config.default_import_path_various == DEFAULT_IMPORT_PATH_VARIOUS
            assert config.more_import_paths == DEFAULT_MORE_IMPORT_PATHS
            assert config.library == Path(".")
            assert config.open_folder_command == ""
            assert config.path_compatibility == PathCompatibilityOption.UNIVERSAL
            assert config.rescan == RescanOption.AUTO
            assert config.tagger == ""
        finally:
            db.dispose()

    def test_database_config_save_load(self):
        db = connection.open(connection.MEMORY)
        try:
            config = Configuration(
                checks={"disc-numbering": {"enabled": False, "discs_in_separate_folders": False, "disctotal_policy": "never"}},
                default_import_path=Template("$album"),
                default_import_path_various=Template("assorted"),
                more_import_paths=(Template("various"),),
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
            assert loaded.default_import_path.template == "$album"
            assert loaded.default_import_path_various.template == "assorted"
            assert isinstance(loaded.more_import_paths, tuple)
            assert len(loaded.more_import_paths) == 1
            assert loaded.more_import_paths[0].template == "various"
            assert loaded.library == Path("/path/to")
            assert loaded.open_folder_command == "open"
            assert loaded.path_compatibility == PathCompatibilityOption.LINUX
            assert loaded.rescan == RescanOption.NEVER
            assert loaded.tagger == "puddletag"
        finally:
            db.dispose()

    def test_database_config_load_ignored_values(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(SettingEntity(name="foo.bar", value=True))
                retr = session.execute(select(SettingEntity).where(SettingEntity.name == "foo.bar")).all()
                assert len(retr) == 1
                assert isinstance(retr[0][0], SettingEntity)
                assert retr[0][0].value
            load(db)
            with Session(db) as session:
                # ignored setting removed from db
                retr = session.execute(select(SettingEntity).where(SettingEntity.name == "foo.bar")).all()
                assert len(retr) == 0
        finally:
            db.dispose()

    def test_database_config_save_overwrite(self):
        db = connection.open(connection.MEMORY)
        try:
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
        finally:
            db.dispose()

    def test_database_config_save_invalid(self):
        db = connection.open(connection.MEMORY)
        try:
            save(db, Configuration({"cover-filename": {"enabled": True, "filename": "cover.*", "jpeg_quality": 90}}))  # ok
            with pytest.raises(ValueError):
                save(db, Configuration({"cover-filename": {"enabled": True, "filename": True, "jpeg_quality": 90}}))  # type: ignore
            with pytest.raises(ValueError):
                save(db, Configuration({"INVALID": {"enabled": True, "filename": "cover.*", "jpeg_quality": 90}}))
            with pytest.raises(ValueError):
                save(db, Configuration({"cover-filename": {"enabled": True, "INVALID": "cover.*", "jpeg_quality": 90}}))
        finally:
            db.dispose()
