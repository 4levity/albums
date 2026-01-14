import json
import re
from click.testing import CliRunner
from albums.cli import entry_point
from .create_library import create_library


albums = [
    {"path": "foo/", "tracks": [{"source_file": "1.mp3", "tags": {"title": "1"}}]},
    {"path": "bar/", "tracks": [{"source_file": "1.flac", "tags": {"title": "1"}}, {"source_file": "2.flac", "tags": {"title": "2"}}]},
]


class TestCli:
    runner = CliRunner()
    library = create_library("cli", albums)

    def run(self, params: list[str]):
        return self.runner.invoke(entry_point.albums, ["--config-file", self.library / "config.ini"] + params)

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

    def test_list_json(self):
        result = self.run(["list", "--json"])
        assert result.exit_code == 0
        result_json = json.loads(result.output)
        assert len(result_json) == 2
        assert result_json[1]["path"] == "foo/"
        assert len(result_json[1]["tracks"]) == 1
        assert result_json[1]["tracks"][0]["source_file"] == "1.mp3"

    def test_filter_regex(self):
        result = self.run(["-r", "-p", "foo", "list", "--json"])
        assert result.exit_code == 0
        result_json = json.loads(result.output)
        assert len(result_json) == 1
        assert result_json[0]["path"] == "foo/"

    def test_add(self):
        result = self.run(["-r", "-p", "foo", "add", "test"])
        assert result.exit_code == 0
        assert result.output.startswith("added album foo/ to collection test")

    def test_filter_group(self):
        result = self.run(["-c", "test", "list", "--json"])
        assert result.exit_code == 0
        result_json = json.loads(result.output)
        assert len(result_json) == 1
        assert result_json[0]["path"] == "foo/"

    def test_remove(self):
        result = self.run(["-r", "-p", "bar", "add", "test"])
        assert result.output.startswith("added album bar/ to collection test")

        result = self.run(["-r", "-p", "foo", "remove", "test"])
        assert result.exit_code == 0
        assert result.output.startswith("removed album foo/ from collection test")

        result = self.run(["-c", "test", "list", "--json"])
        result_json = json.loads(result.output)
        assert len(result_json) == 1
        assert result_json[0]["path"] == "bar/"  # foo was removed
