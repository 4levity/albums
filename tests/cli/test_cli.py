import json
import os
import re
import shutil

import pytest

from albums.picture.info import PictureInfo
from albums.tagger.types import BasicTag
from albums.types import Album, PictureFile, Track

from .. import helpers
from ..fixtures.create_library import create_library, test_data_path

albums = [
    Album(
        path="foo" + os.sep,
        tracks=[Track(filename="1.mp3", tag={BasicTag.TITLE: "1"})],
        picture_files=[PictureFile(filename="folder.png", picture_info=PictureInfo("ignored", 400, 400, 24, 0, b""))],
    ),
    Album(
        path="bar" + os.sep,
        tracks=[
            Track(filename="1.flac", tag={BasicTag.TITLE: "1"}),
            Track(filename="2.flac", tag={BasicTag.TITLE: "2"}),
        ],
    ),
]


class TestCli:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestCli.library = create_library("cli", albums)

    def run(self, params: list[str], init=False):
        if init:
            helpers.init_db(TestCli.library)
        return helpers.run(params, TestCli.library)

    def test_help(self):
        result = self.run(["--help"])
        assert result.exit_code == 0
        assert "Usage: albums [OPTIONS] COMMAND [ARGS]" in result.output

    def test_scan(self):
        result = helpers.init_db(TestCli.library)
        assert result.exit_code == 0
        assert "creating database" in result.output
        result = self.run(["-v", "scan"])
        assert result.exit_code == 0
        assert "scanned 3 folders" in result.output

        result = self.run(["scan"])
        assert result.exit_code == 0
        assert not result.output.startswith("creating database")

    def test_list(self):
        self.run(["scan"], init=True)
        result = self.run(["list"])
        assert result.exit_code == 0
        assert re.search("bar.+00:00.+\\d+ Bytes.+total: \\d+.*", result.output, re.MULTILINE | re.DOTALL)

    def test_scan_remove(self):
        result = self.run(["-v", "scan"], init=True)
        assert result.exit_code == 0
        assert "scanned 3 folders" in result.output

        shutil.rmtree(TestCli.library / "foo")

        result = self.run(["-v", "scan"])
        assert "removed: 1" in result.output
        result = self.run(["list"])
        assert "foo" not in result.output

    def test_check(self):
        result = self.run(["check", "--default", "album-tag"], init=True)
        assert result.exit_code == 0
        assert f'1 tracks missing album tag : "foo{os.sep}"' in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output

    def test_check_automatically_enabled_dependencies(self):
        result = self.run(["check", "disc-numbering"], init=True)
        assert result.exit_code == 0
        assert "automatically enabling check invalid-track-or-disc-number" in result.output

    def test_ignore_check(self):
        self.run(["scan"], init=True)
        result = self.run(["-p", "foo" + os.sep, "ignore", "album-tag"])
        assert result.exit_code == 0
        assert f"album foo{os.sep} - ignore album-tag" in result.output

        result = self.run(["check", "--default", "album-tag"])
        assert result.exit_code == 0
        assert "foo" + os.sep not in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output

    def test_notice_check_not_ignored(self):
        self.run(["scan"], init=True)
        result = self.run(["-rp", "(foo|bar)", "notice", "--force", "album-tag"])  # filtered so that album names will not be suppressed
        assert result.exit_code == 0
        assert f"album foo{os.sep} was already not ignoring album-tag" in result.output
        assert f"album bar{os.sep} was already not ignoring album-tag" in result.output

    def test_notice_check(self):
        self.run(["scan"], init=True)
        result = self.run(["check", "--default"])
        assert f'1 tracks missing album tag : "foo{os.sep}"' in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output
        self.run(["-p", "foo" + os.sep, "ignore", "album-tag"])
        result = self.run(["check", "--default"])
        assert f'1 tracks missing album tag : "foo{os.sep}"' not in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output

        result = self.run(["notice", "--force", "album-tag"])
        assert result.exit_code == 0
        assert f"album foo{os.sep} will stop ignoring album-tag" in result.output

        result = self.run(["check", "--default"])
        assert f'1 tracks missing album tag : "foo{os.sep}"' in result.output
        assert f'2 tracks missing album tag : "bar{os.sep}"' in result.output

    def test_check_automatic_fix(self):
        result = self.run(["check", "--automatic", "album-tag"], init=True)
        assert result.exit_code == 0
        assert f'"foo{os.sep}" - 1 tracks missing album tag' in result.output
        assert f'"bar{os.sep}" - 2 tracks missing album tag' in result.output
        assert "setting album on 1.flac" in result.output

        result = self.run(["--verbose", "scan"])
        assert result.exit_code == 0
        assert "unchanged: 2" in result.output

        result = self.run(["check", "--automatic", "album-tag"])
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

    def test_filter_path_regex_match(self):
        self.run(["scan"], init=True)
        result = self.run(["-rm", "path=.oo", "list", "--json"])
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

    def test_filter_collection_match(self):
        self.run(["scan"], init=True)
        result = self.run(["-rp", "foo", "add", "test"])

        result = self.run(["-m", "collection=test", "list", "--json"])
        obj = json.loads(result.output)
        assert len(obj) == 1
        assert obj[0]["path"] == "foo" + os.sep

    def test_remove_collection(self):
        self.run(["scan"], init=True)
        result = self.run(["add", "test"])  # add all
        assert result.exit_code == 0
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
        assert "Copying 2 files" in result.output
        assert "will delete 2 paths" in result.output
        assert (dest / "bar").is_dir()
        assert (dest / "bar" / "1.flac").is_file()
        assert not (dest / "other").exists()

        result = self.run(["-c", "test", "sync", str(dest), "--delete", "--force"])
        assert result.exit_code == 0
        assert "no tracks to copy (skipped 2)" in result.output

    def test_import_automatic(self):
        self.run(["scan"], init=True)
        result = self.run(["list"])
        assert "baz" not in result.output

        new_album = Album(
            path="baz" + os.sep,
            tracks=[Track(filename="1.flac", tag={BasicTag.TITLE: "1", BasicTag.TRACKNUMBER: "01", BasicTag.ALBUM: "baz", BasicTag.ARTIST: "baz"})],
        )
        src = create_library("cli_import", [new_album])
        result = self.run(["-v", "import", "--automatic", str(src)])
        assert result.exit_code == 0
        assert "automatically fixing track-filename" in result.output
        assert "Copying 1 file" in result.output

        self.run(["scan"])
        result = self.run(["list"])
        assert "baz" in result.output

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
