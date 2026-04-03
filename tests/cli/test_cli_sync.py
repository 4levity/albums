import json
import os
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
        tracks=[Track(filename="1.mp3", tag={BasicTag.TITLE: "1", BasicTag.ARTIST: "a"})],
        picture_files=[PictureFile(filename="folder.png", picture_info=PictureInfo("ignored", 400, 400, 24, 0, b""))],
    ),
    Album(
        path="bar" + os.sep,
        tracks=[
            Track(filename="1.flac", tag={BasicTag.TITLE: "one", BasicTag.ALBUM: "bar", BasicTag.ARTIST: "foo"}),
            Track(filename="2.flac", tag={BasicTag.TITLE: "two", BasicTag.ALBUM: "bar", BasicTag.ARTIST: "foo"}),
        ],
    ),
]


class TestCliSync:
    def run(self, params: list[str]):
        return helpers.run(params, TestCliSync.library)

    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestCliSync.library = create_library("cli_sync", albums)
        helpers.init_db(TestCliSync.library)
        TestCliSync.dest = test_data_path / "cli_sync_filter_dest"
        shutil.rmtree(TestCliSync.dest, ignore_errors=True)
        os.makedirs(TestCliSync.dest)

    def test_sync_filter_no_destination(self):
        result = self.run(["-rp", "bar", "sync"])
        assert result.exit_code == 1
        assert "specify the destination directory" in result.output

    def test_sync_relative_destination(self):
        result = self.run(["-rp", "bar", "sync", "."])
        assert result.exit_code == 1
        assert "must be absolute" in result.output or "must include the drive letter" in result.output

    def test_sync_nonexistent_destination(self):
        result = self.run(["-rp", "bar", "sync", str(TestCliSync.dest / "missing")])
        assert result.exit_code == 1
        assert "destination path must exist" in result.output

    def test_sync_destination_is_file(self):
        with open(TestCliSync.dest / "file", "w"):
            pass
        result = self.run(["-rp", "bar", "sync", str(TestCliSync.dest / "file")])
        assert result.exit_code == 1
        assert "destination path is not a directory" in result.output

    def test_sync_filter_to_path(self):
        result = self.run(["-rp", "bar", "sync", str(TestCliSync.dest)])
        assert result.exit_code == 0
        assert "Copying 1 album" in result.output
        assert (TestCliSync.dest / "bar").is_dir()
        assert (TestCliSync.dest / "bar" / "1.flac").is_file()
        assert (TestCliSync.dest / "bar" / "2.flac").is_file()

    def test_sync_existing(self):
        dest = test_data_path / "cli_sync_existing_dest"
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest)

        result = self.run(["-rp", "bar", "sync", str(dest)])
        assert result.exit_code == 0
        assert (dest / "bar" / "1.flac").is_file()

        result = self.run(["-rp", "bar", "sync", str(dest)])
        assert result.exit_code == 0
        assert "Skipping 2 existing tracks" in result.output
        assert "nothing to copy" in result.output

    def test_sync_delete_extraneous(self):
        os.makedirs(TestCliSync.dest / "other")
        with open(TestCliSync.dest / "other" / "baz.txt", "w"):
            pass

        result = self.run(["-rp", "bar", "sync", str(TestCliSync.dest), "--delete", "--force"])
        assert result.exit_code == 0
        assert "Copying 1 album" in result.output
        assert "will delete 2 paths" in result.output
        assert (TestCliSync.dest / "bar").is_dir()
        assert (TestCliSync.dest / "bar" / "1.flac").is_file()
        assert (TestCliSync.dest / "bar" / "2.flac").is_file()
        assert not (TestCliSync.dest / "other").exists()

    def test_sync_defined_by_collection(self):
        result = self.run(["-rp", "bar", "add", "test"])
        dest = {"collection": "test", "path_root": str(TestCliSync.dest), "relpath_template_artist": f"$artist{os.sep}$album"}
        config_file = TestCliSync.library / "config.json"
        with open(config_file, "w") as f:
            f.write(json.dumps({"settings.sync_destinations": [dest]}))
        result = self.run(["config", "--import", str(config_file)])
        assert result.exit_code == 0

        result = self.run(["sync", "test"])
        assert result.exit_code == 0
        assert "Copying 1 album" in result.output
        assert (TestCliSync.dest / "foo" / "bar").is_dir()  # uses $album/$artist template from config set above
        assert (TestCliSync.dest / "foo" / "bar" / "1.flac").is_file()
        assert (TestCliSync.dest / "foo" / "bar" / "2.flac").is_file()

    def test_sync_defined_by_path(self):
        result = self.run(["-rp", "bar", "add", "test"])
        dest = {"collection": "test", "path_root": str(TestCliSync.dest), "relpath_template_artist": f"$artist{os.sep}$album"}
        config_file = TestCliSync.library / "config.json"
        with open(config_file, "w") as f:
            f.write(json.dumps({"settings.sync_destinations": [dest]}))
        result = self.run(["config", "--import", str(config_file)])
        assert result.exit_code == 0

        result = self.run(["sync", str(TestCliSync.dest)])
        assert result.exit_code == 0
        assert (TestCliSync.dest / "foo" / "bar" / "1.flac").is_file()

    def test_sync_select_one(self, mocker):
        result = self.run(["-rp", "bar", "add", "test"])
        dest = {"collection": "test", "path_root": str(TestCliSync.dest), "relpath_template_artist": f"$artist{os.sep}$album"}
        config_file = TestCliSync.library / "config.json"
        with open(config_file, "w") as f:
            f.write(json.dumps({"settings.sync_destinations": [dest]}))
        result = self.run(["config", "--import", str(config_file)])
        assert result.exit_code == 0

        mock_choice = mocker.patch("albums.cli.sync.choice", return_value=0)
        result = self.run(["sync"])
        assert result.exit_code == 0
        assert (TestCliSync.dest / "foo" / "bar" / "1.flac").is_file()
        assert mock_choice.call_count == 1

    def test_sync_select_ambiguous(self, mocker):
        result = self.run(["-rp", "bar", "add", "test"])
        dest1 = {"collection": "test", "path_root": str(TestCliSync.dest), "relpath_template_artist": f"$artist{os.sep}$album"}
        dest2 = {"collection": "test2", "path_root": str(TestCliSync.dest), "relpath_template_artist": f"$artist{os.sep}$album"}
        config_file = TestCliSync.library / "config.json"
        with open(config_file, "w") as f:
            f.write(json.dumps({"settings.sync_destinations": [dest1, dest2]}))
        result = self.run(["config", "--import", str(config_file)])
        assert result.exit_code == 0

        mock_choice = mocker.patch("albums.cli.sync.choice", return_value=0)
        result = self.run(["sync", str(TestCliSync.dest)])
        assert result.exit_code == 0
        assert (TestCliSync.dest / "foo" / "bar" / "1.flac").is_file()
        assert mock_choice.call_count == 1

    def test_sync_select_two(self, mocker):
        result = self.run(["-rp", "bar", "add", "test"])
        dest1 = {"collection": "test", "path_root": str(TestCliSync.dest), "relpath_template_artist": f"$artist{os.sep}$album"}
        dest2 = {"collection": "test2", "path_root": str(TestCliSync.dest), "relpath_template_artist": f"$artist{os.sep}$album"}
        config_file = TestCliSync.library / "config.json"
        with open(config_file, "w") as f:
            f.write(json.dumps({"settings.sync_destinations": [dest1, dest2]}))
        result = self.run(["config", "--import", str(config_file)])
        assert result.exit_code == 0

        mock_choice = mocker.patch("albums.cli.sync.choice", return_value=0)
        result = self.run(["sync"])
        assert result.exit_code == 0
        assert (TestCliSync.dest / "foo" / "bar" / "1.flac").is_file()
        assert mock_choice.call_count == 1

    def test_sync_both_filter_and_preconfigured(self):
        dest = {"collection": "test", "path_root": str(TestCliSync.dest), "relpath_template_artist": f"$artist{os.sep}$album"}
        config_file = TestCliSync.library / "config.json"
        with open(config_file, "w") as f:
            f.write(json.dumps({"settings.sync_destinations": [dest]}))
        result = self.run(["config", "--import", str(config_file)])
        assert result.exit_code == 0

        result = self.run(["-rp", "bar", "sync", "test"])
        assert result.exit_code == 1
        assert "pre-configured destination, do not specify any album filters" in result.output
