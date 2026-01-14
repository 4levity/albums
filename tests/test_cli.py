import json
import os
import re
import shutil
from click.testing import CliRunner
import pytest
from albums.cli import entry_point
from .create_library import create_library, test_data_path


albums = [
    {"path": "foo/", "tracks": [{"filename": "1.mp3", "tags": {"title": "1"}}]},
    {"path": "bar/", "tracks": [{"filename": "1.flac", "tags": {"title": "1"}}, {"filename": "2.flac", "tags": {"title": "2"}}]},
]


# Integration tests with persistent database
class TestCli:
    @pytest.fixture(scope="module", autouse=True)
    def setup_cli_tests(self):
        TestCli.runner = CliRunner()
        TestCli.library = create_library("cli", albums)
        with open(TestCli.library / "config.ini", "w") as config_file:  # create a config.ini for cli invocation
            config_file.write(
                f"""[locations]
library={TestCli.library}
database={TestCli.library / "albums.db"}
"""
            )

    def run(self, params: list[str]):
        return TestCli.runner.invoke(entry_point.albums, ["--config-file", TestCli.library / "config.ini"] + params)

    def test_help(self):
        result = self.run(["--help"])
        assert result.exit_code == 0
        assert result.output.startswith("Usage: albums [OPTIONS] COMMAND [ARGS]")

    def test_scan(self):
        result = self.run(["scan"])
        assert result.exit_code == 0
        assert result.output.startswith("creating database")
        assert "finding folders in /home/ivan/src/albums/tests/libraries/cli" in result.output

    def test_list(self):
        result = self.run(["list"])
        assert result.exit_code == 0
        assert re.search("album: bar/ \\(\\d+ Bytes\\).*total size: \\d+.*", result.output, re.MULTILINE | re.DOTALL)

    def test_check(self):
        result = self.run(["check", "--default"])
        assert result.exit_code == 0
        assert "tracks missing required tags {'artist': 1} : foo/" in result.output
        assert "tracks missing required tags {'artist': 2} : bar/" in result.output

    def test_list_json(self):
        result = self.run(["list", "--json"])
        assert result.exit_code == 0
        result_json = json.loads(result.output)
        assert len(result_json) == 2
        assert result_json[1]["path"] == "foo/"
        assert len(result_json[1]["tracks"]) == 1
        assert result_json[1]["tracks"][0]["filename"] == "1.mp3"

    def test_filter_path_regex(self):
        result = self.run(["-r", "-p", ".oo", "list", "--json"])
        assert result.exit_code == 0
        result_json = json.loads(result.output)
        assert len(result_json) == 1
        assert result_json[0]["path"] == "foo/"

    def test_add_collection(self):
        result = self.run(["-r", "-p", "foo", "add", "test"])
        assert result.exit_code == 0
        assert result.output.startswith("added album foo/ to collection test")

    def test_filter_collection(self):
        result = self.run(["-c", "test", "list", "--json"])
        assert result.exit_code == 0
        result_json = json.loads(result.output)
        assert len(result_json) == 1
        assert result_json[0]["path"] == "foo/"

    def test_remove_collection(self):
        result = self.run(["-r", "-p", "bar", "add", "test"])
        assert result.output.startswith("added album bar/ to collection test")

        result = self.run(["-r", "-p", "foo", "remove", "test"])
        assert result.exit_code == 0
        assert result.output.startswith("removed album foo/ from collection test")

        result = self.run(["-c", "test", "list", "--json"])
        result_json = json.loads(result.output)
        assert len(result_json) == 1
        assert result_json[0]["path"] == "bar/"  # foo was removed

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
