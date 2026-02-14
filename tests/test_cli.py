import json
import os
import re
import shutil

import pytest
from click.testing import CliRunner

from albums.cli import entry_point
from albums.types import Album, Picture, PictureType, Track

from .fixtures.create_library import create_library, test_data_path

albums = [
    Album("foo" + os.sep, [Track("1.mp3", {"title": ["1"]})], [], [], {"folder.png": Picture(PictureType.COVER_FRONT, "ignored", 400, 400, 0, b"")}),
    Album("bar" + os.sep, [Track("1.flac", {"title": ["1"]}), Track("2.flac", {"title": ["2"]})]),
]


# Integration tests with persistent database that is used between tests - must run all (most) in order
# TODO set up fixtures for these tests to run independently, or create explicit dependencies
class TestCli:
    @pytest.fixture(scope="module", autouse=True)
    def setup_cli_tests(self):
        TestCli.runner = CliRunner()
        TestCli.library = create_library("cli", albums)
        with open(TestCli.library / "config.toml", "w") as config_file:  # create a config.toml for cli invocation
            config_file.write(
                f"""[locations]
library="{str(TestCli.library).replace("\\", "\\\\")}"
database="{str(TestCli.library / "albums.db").replace("\\", "\\\\")}"
"""
            )

    def run(self, params: list[str], config_filename="config.toml"):
        return TestCli.runner.invoke(entry_point.albums_group, ["--config-file", TestCli.library / config_filename] + params)

    def test_help(self):
        result = self.run(["--help"])
        assert result.exit_code == 0
        assert "Usage: albums [OPTIONS] COMMAND [ARGS]" in result.output

    def test_scan(self):
        result = self.run(["scan"])
        assert result.exit_code == 0
        assert result.output.startswith("creating database")
        assert "Scanning" in result.output

        result = self.run(["scan"])
        assert result.exit_code == 0
        assert not result.output.startswith("creating database")

    def test_list(self):
        result = self.run(["list"])
        assert result.exit_code == 0
        assert re.search("bar.+00:00.+\\d+ Bytes.+total: \\d+.*", result.output, re.MULTILINE | re.DOTALL)

    def test_check(self):
        result = self.run(["check", "--default", "album_tag"])
        assert result.exit_code == 0
        assert f'1 tracks missing album tag : "foo{os.sep}"' in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output

    def test_check_automatically_enabled_dependencies(self):
        config_filename = "config_invalid_number_disabled.toml"
        with open(TestCli.library / config_filename, "w") as config_file:
            config_file.write(
                f"""[locations]
library="{str(TestCli.library).replace("\\", "\\\\")}"
database="{str(TestCli.library / "albums.db").replace("\\", "\\\\")}"
checks.invalid_track_or_disc_number.enabled = false
"""
            )

        result = self.run(["check", "disc_numbering"], config_filename)
        assert result.exit_code == 0
        assert "automatically enabling check invalid_track_or_disc_number" in result.output

    def test_ignore_check(self):
        result = self.run(["-p", "foo" + os.sep, "ignore", "album_tag"])
        assert result.exit_code == 0
        assert f"album foo{os.sep} - ignore album_tag" in result.output

        result = self.run(["check", "--default", "album_tag"])
        assert result.exit_code == 0
        assert "foo" + os.sep not in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output

    def test_notice_check(self):
        result = self.run(["notice", "--force", "album_tag"])
        assert result.exit_code == 0
        assert f"album foo{os.sep} will stop ignoring album_tag" in result.output

        result = self.run(["check", "--default"])
        assert result.exit_code == 0
        assert f'1 tracks missing album tag : "foo{os.sep}"' in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output

    def ftest_check_automatic_fix(self):
        result = self.run(["check", "--automatic", "album_tag"])
        assert result.exit_code == 0
        assert '"foo" + os.sep - 1 tracks missing album tag' in result.output
        assert '"bar" + os.sep - 2 tracks missing album tag' in result.output
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
        result = self.run(["list", "--json"])
        assert result.exit_code == 0
        result_json = json.loads(result.output)
        assert len(result_json) == 2
        assert result_json[1]["path"] == "foo" + os.sep
        assert len(result_json[1]["tracks"]) == 1
        assert result_json[1]["tracks"][0]["filename"] == "1.mp3"

    def test_filter_path_regex(self):
        result = self.run(["-r", "-p", ".oo", "list", "--json"])
        assert result.exit_code == 0
        result_json = json.loads(result.output)
        assert len(result_json) == 1
        assert result_json[0]["path"] == "foo" + os.sep

    def test_add_collection(self):
        result = self.run(["-r", "-p", "foo", "add", "test"])
        assert result.exit_code == 0
        assert result.output.startswith(f"added album foo{os.sep} to collection test")

    def test_filter_collection(self):
        result = self.run(["-c", "test", "list", "--json"])
        assert result.exit_code == 0
        result_json = json.loads(result.output)
        assert len(result_json) == 1
        assert result_json[0]["path"] == "foo" + os.sep

    def test_remove_collection(self):
        result = self.run(["-r", "-p", "bar", "add", "test"])
        assert result.output.startswith(f"added album bar{os.sep} to collection test")

        result = self.run(["-r", "-p", "foo", "remove", "test"])
        assert result.exit_code == 0
        assert result.output.startswith(f"removed album foo{os.sep} from collection test")

        result = self.run(["-c", "test", "list", "--json"])
        result_json = json.loads(result.output)
        assert len(result_json) == 1
        assert result_json[0]["path"] == "bar" + os.sep  # foo was removed

    def test_sync(self):
        dest = test_data_path / "cli_sync"
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest / "other")
        with open(dest / "other" / "baz.txt", "w"):
            pass

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
