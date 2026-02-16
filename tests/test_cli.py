import json
import os
import re
import shutil

import pytest

from albums.types import Album, Picture, PictureType, Track

from . import helpers
from .fixtures.create_library import create_library, test_data_path

albums = [
    Album("foo" + os.sep, [Track("1.mp3", {"title": ["1"]})], [], [], {"folder.png": Picture(PictureType.COVER_FRONT, "ignored", 400, 400, 0, b"")}),
    Album("bar" + os.sep, [Track("1.flac", {"title": ["1"]}), Track("2.flac", {"title": ["2"]})]),
]


class TestCli:
    @pytest.fixture(scope="function", autouse=True)
    def setup_cli_tests(self):
        TestCli.library = create_library("cli", albums)

    def run(self, params: list[str], init=False):
        return helpers.run(params, TestCli.library, init)

    def test_help(self):
        result = self.run(["--help"])
        assert result.exit_code == 0
        assert "Usage: albums [OPTIONS] COMMAND [ARGS]" in result.output

    def test_scan(self):
        result = self.run(["scan"], init=True)
        assert result.exit_code == 0
        assert result.output.startswith("creating database")
        assert "Scanning" in result.output

        result = self.run(["scan"])
        assert result.exit_code == 0
        assert not result.output.startswith("creating database")

    def test_list(self):
        self.run(["scan"], init=True)
        result = self.run(["list"])
        assert result.exit_code == 0
        assert re.search("bar.+00:00.+\\d+ Bytes.+total: \\d+.*", result.output, re.MULTILINE | re.DOTALL)

    def test_check(self):
        result = self.run(["check", "--default", "album_tag"], init=True)
        assert result.exit_code == 0
        assert f'1 tracks missing album tag : "foo{os.sep}"' in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output

    def test_check_automatically_enabled_dependencies(self):
        result = self.run(["check", "disc_numbering"], init=True)
        assert result.exit_code == 0
        assert "automatically enabling check invalid_track_or_disc_number" in result.output

    def test_ignore_check(self):
        self.run(["scan"], init=True)
        result = self.run(["-p", "foo" + os.sep, "ignore", "album_tag"])
        assert result.exit_code == 0
        assert f"album foo{os.sep} - ignore album_tag" in result.output

        result = self.run(["check", "--default", "album_tag"])
        assert result.exit_code == 0
        assert "foo" + os.sep not in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output

    def test_notice_check_not_ignored(self):
        self.run(["scan"], init=True)
        result = self.run(["-rp", "(foo|bar)", "notice", "--force", "album_tag"])  # filtered so that album names will not be suppressed
        assert result.exit_code == 0
        assert f"album foo{os.sep} was already not ignoring album_tag" in result.output
        assert f"album bar{os.sep} was already not ignoring album_tag" in result.output

    def test_notice_check(self):
        self.run(["scan"], init=True)
        result = self.run(["check", "--default"])
        assert f'1 tracks missing album tag : "foo{os.sep}"' in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output
        self.run(["-p", "foo" + os.sep, "ignore", "album_tag"])
        result = self.run(["check", "--default"])
        assert f'1 tracks missing album tag : "foo{os.sep}"' not in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output

        result = self.run(["notice", "--force", "album_tag"])
        assert result.exit_code == 0
        assert f"album foo{os.sep} will stop ignoring album_tag" in result.output

        result = self.run(["check", "--default"])
        assert f'1 tracks missing album tag : "foo{os.sep}"' in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output

    def test_check_automatic_fix(self):
        result = self.run(["check", "--automatic", "album_tag"], init=True)
        assert result.exit_code == 0
        assert f'"foo{os.sep}" - 1 tracks missing album tag' in result.output
        assert f'"bar{os.sep}" - 2 tracks missing album tag' in result.output
        assert "setting album on 1.flac" in result.output

        result = self.run(["--verbose", "scan"])
        assert result.exit_code == 0
        assert "unchanged: 2" in result.output

        result = self.run(["check", "--automatic", "album_tag"])
        assert result.exit_code == 0
        assert "foo" + os.sep not in result.output
        assert "bar" + os.sep not in result.output
        assert "1.flac" not in result.output

    def test_list_json(self):
        self.run(["scan"], init=True)
        result = self.run(["list", "--json"])
        assert result.exit_code == 0
        result_json = json.loads(result.output)
        assert len(result_json) == 2
        assert result_json[1]["path"] == "foo" + os.sep
        assert len(result_json[1]["tracks"]) == 1
        assert result_json[1]["tracks"][0]["filename"] == "1.mp3"

    def test_list_json_empty(self):
        shutil.rmtree(TestCli.library / albums[0].path)
        shutil.rmtree(TestCli.library / albums[1].path)
        self.run(["scan"], init=True)
        result = self.run(["list", "--json"])
        assert result.exit_code == 0
        obj = json.loads(result.output)
        assert obj == []

    def test_filter_path_regex(self):
        self.run(["scan"], init=True)
        result = self.run(["-rp", ".oo", "list", "--json"])
        assert result.exit_code == 0
        obj = json.loads(result.output)
        assert len(obj) == 1
        assert obj[0]["path"] == "foo" + os.sep

    def test_add_collection(self):
        self.run(["scan"], init=True)
        result = self.run(["-rp", "foo", "add", "test"])
        assert result.exit_code == 0
        assert result.output.startswith(f"added album foo{os.sep} to collection test")

    def test_filter_collection(self):
        self.run(["scan"], init=True)
        result = self.run(["-rp", "foo", "add", "test"])

        result = self.run(["-c", "test", "list", "--json"])
        assert result.exit_code == 0
        obj = json.loads(result.output)
        assert len(obj) == 1
        assert obj[0]["path"] == "foo" + os.sep

    def test_remove_collection(self):
        self.run(["scan"], init=True)
        result = self.run(["add", "test"])  # add all
        assert f"added album foo{os.sep} to collection test" in result.output
        assert f"added album bar{os.sep} to collection test" in result.output

        result = self.run(["-rp", "foo", "remove", "test"])
        assert result.exit_code == 0
        assert f"removed album foo{os.sep} from collection test" in result.output

        result = self.run(["-c", "test", "list", "--json"])
        obj = json.loads(result.output)
        assert len(obj) == 1
        assert obj[0]["path"] == "bar" + os.sep  # foo was removed

    def test_sync(self):
        dest = test_data_path / "cli_sync"
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest / "other")
        with open(dest / "other" / "baz.txt", "w"):
            pass
        self.run(["scan"], init=True)
        self.run(["-rp", "bar", "add", "test"])

        result = self.run(["-c", "test", "sync", str(dest), "--delete", "--force"])
        assert result.exit_code == 0
        assert "copying 2 tracks" in result.output
        assert "will delete 2 paths" in result.output
        assert (dest / "bar").is_dir()
        assert (dest / "bar" / "1.flac").is_file()
        assert not (dest / "other").exists()

        result = self.run(["-c", "test", "sync", str(dest), "--delete", "--force"])
        assert result.exit_code == 0
        assert "no tracks to copy (skipped 2)" in result.output

    def test_sql(self):
        self.run(["scan"], init=True)
        result = self.run(["sql", "--json", "SELECT * from album ORDER BY path;"])
        assert result.exit_code == 0
        result = json.loads(result.output)
        assert result[0][1] == "bar" + os.sep
        assert result[1][1] == "foo" + os.sep

        result = self.run(["sql", "SELECT * from album;"])
        assert result.exit_code == 0
        assert "foo" + os.sep in result.output
        assert "album_id" in result.output  # shows column names
        assert "path" in result.output
