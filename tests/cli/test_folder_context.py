import json
import os

import pytest
from click.testing import CliRunner

from albums.app import Context
from albums.cli import entry_point
from albums.cli.cli_context import enter_folder_context
from albums.config import config_load, config_save
from albums.database import MEMORY, db_open
from albums.entities import Album, Track

from .. import helpers
from ..fixtures.create_library import create_library

album1 = Album(path="foo" + os.sep, tracks=[Track(filename="1.mp3")])
album2 = Album(path="bar" + os.sep, tracks=[Track(filename="1.flac")])


class TestFolderContext:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestFolderContext.library = create_library("cli", [album1, album2])

    def test_zero_config(self, monkeypatch, tmp_path):
        # point the default db lookup at a nonexistent file so a real user database is not loaded and migrated
        monkeypatch.setenv("ALBUMS_DB", str(tmp_path / "albums.db"))
        result = CliRunner().invoke(entry_point.albums_group, ["--dir", str(TestFolderContext.library), "list", "--json"])
        assert result.exit_code == 0
        obj = json.loads(result.output)
        assert len(obj) == 2
        assert obj[0]["path"] == "bar" + os.sep
        assert obj[1]["path"] == "foo" + os.sep

    def test_with_library(self):
        library = TestFolderContext.library / album1.path
        other_dir = TestFolderContext.library / album2.path

        helpers.init_db_cached(library, [album1])
        result = helpers.run(["list"], library)
        assert "foo" in result.output

        result = helpers.run(["--dir", str(other_dir), "list", "--json"], library)
        obj = json.loads(result.output)
        assert len(obj) == 1
        assert obj[0]["path"] == "."
        assert obj[0]["tracks"][0]["filename"] == album2.tracks[0].filename

    def test_folder_db_has_context_config(self, tmp_path):
        # enter_folder_context copies the context config into the in-memory database, so checks that read
        # settings from the db (e.g. track-filename borrowing zero-pad-numbers) see the persisted values
        ctx = Context()
        ctx.db = db_open(MEMORY)
        ctx.config.checks["zero-pad-numbers"]["enabled"] = False  # differs from the default
        config_save(ctx.db, ctx.config)
        folder = tmp_path / "album"
        folder.mkdir()
        enter_folder_context(ctx, str(folder))
        assert config_load(ctx.db).checks["zero-pad-numbers"]["enabled"] is False
