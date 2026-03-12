import json
import os

import pytest
from click.testing import CliRunner

from albums.cli import entry_point
from albums.database.models import AlbumEntity, TrackEntity

from .. import helpers
from ..fixtures.create_library import create_library

album1 = AlbumEntity(path="foo" + os.sep, tracks=[TrackEntity(filename="1.mp3")])
album2 = AlbumEntity(path="bar" + os.sep, tracks=[TrackEntity(filename="1.flac")])


class TestFolderContext:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestFolderContext.library = create_library("cli", [album1, album2])

    def test_zero_config(self):
        result = CliRunner().invoke(entry_point.albums_group, ["--dir", str(TestFolderContext.library), "list", "--json"])
        assert result.exit_code == 0
        obj = json.loads(result.output)
        assert len(obj) == 2
        assert obj[0]["path"] == "bar" + os.sep
        assert obj[1]["path"] == "foo" + os.sep

    def test_with_library(self):
        library = TestFolderContext.library / album1.path
        other_dir = TestFolderContext.library / album2.path

        result = helpers.run(["list"], library, True)
        assert "foo" in result.output

        result = helpers.run(["--dir", str(other_dir), "list", "--json"], library)
        obj = json.loads(result.output)
        assert len(obj) == 1
        assert obj[0]["path"] == "."
        assert obj[0]["tracks"][0]["filename"] == album2.tracks[0].filename
