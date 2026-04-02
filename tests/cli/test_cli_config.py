import json
import os
import re

import pytest

from albums.config import DEFAULT_MORE_IMPORT_PATHS

from .. import helpers
from ..fixtures.create_library import create_library


class TestCliConfig:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestCliConfig.library = create_library("cli_cfg", [])

    def run(self, params: list[str], init=False):
        if init:
            helpers.init_db(TestCliConfig.library)
        return helpers.run(params, TestCliConfig.library)

    def test_config(self):
        def assert_setting(output: str, name: str, value: str):
            assert re.search(f"│ {re.escape(name)}\\s+│[*\\s]+| {re.escape(value)}", output)

        result = self.run(["config", "--show"], init=True)
        assert_setting(result.output, "settings.library", str(TestCliConfig.library)[:16])
        assert_setting(result.output, "settings.rescan", "auto")
        assert_setting(result.output, "settings.open_folder_command", " ")
        assert_setting(result.output, "cover-dimensions.min_pixels", "100")
        assert_setting(result.output, "cover-dimensions.squareness", "0.98")
        assert_setting(result.output, "cover-filename.enabled", "True")

        result = self.run(["config", "settings.library=."])
        assert result.exit_code == 0
        assert "settings.library = ." in result.output
        result = self.run(["config", "settings.rescan=never"])
        assert "settings.rescan = never" in result.output
        result = self.run(["config", "settings.tagger=mp3tag"])
        assert "settings.tagger = mp3tag" in result.output
        result = self.run(["config", "settings.open_folder_command=xdg-open"])
        assert "settings.open_folder_command = xdg-open" in result.output

        result = self.run(["config", "cover-dimensions.min_pixels=42"])
        assert "cover-dimensions.min_pixels = 42" in result.output
        result = self.run(["config", "cover-dimensions.squareness=0.42"])
        assert "cover-dimensions.squareness = 0.42" in result.output
        result = self.run(["config", "cover-filename.enabled=False"])
        assert "cover-filename.enabled = False" in result.output

        result = self.run(["config", "--show"])
        assert_setting(result.output, "settings.library", ".")
        assert_setting(result.output, "settings.rescan", "never")
        assert_setting(result.output, "settings.tagger", "mp3tag")
        assert_setting(result.output, "settings.open_folder_command", "xdg-open")
        assert_setting(result.output, "cover-dimensions.min_pixels", "42")
        assert_setting(result.output, "cover-dimensions.squareness", "0.42")
        assert_setting(result.output, "cover-filename.enabled", "False")
        self.run(["config", "settings.library", str(TestCliConfig.library)])

    def test_config_get_setting(self):
        result = self.run(["config", "settings.library"], init=True)
        assert result.exit_code == 0
        assert f"settings.library = {str(TestCliConfig.library)}" in result.output

        result = self.run(["config", "settings.more_import_paths"])
        assert result.exit_code == 0
        assert f"settings.more_import_paths = {','.join(p.template for p in DEFAULT_MORE_IMPORT_PATHS)}" in result.output

    def test_config_id3v1(self):
        result = self.run(["config", "settings.id3v1"], init=True)
        assert "settings.id3v1 = UPDATE" in result.output
        result = self.run(["config", "settings.id3v1=CREATE"])
        assert "settings.id3v1 = CREATE" in result.output
        result = self.run(["config", "settings.id3v1=Remove"])
        assert "settings.id3v1 = REMOVE" in result.output
        result = self.run(["config", "settings.id3v1"])
        assert "settings.id3v1 = REMOVE" in result.output
        result = self.run(["config", "settings.id3v1=update"])
        assert "settings.id3v1 = UPDATE" in result.output

    def test_config_long_setting_value(self):
        more_paths = ",".join(["a"] * 100)
        result = self.run(["config", f"settings.more_import_paths={more_paths}"], init=True)
        assert f"settings.more_import_paths = {more_paths}" in result.output

        result = self.run(["config", "settings.more_import_paths"])
        assert f"settings.more_import_paths = {more_paths}" in result.output

    def test_config_invalid(self):
        result = self.run(["config", "settings.foo=bar"], init=True)
        assert result.exit_code == 1
        assert "not a valid setting" in result.output

        result = self.run(["config", "library=."])
        assert result.exit_code == 1
        assert "invalid setting" in result.output

        result = self.run(["config", "foo.enabled=true"])
        assert result.exit_code == 1
        assert "foo is not a valid check name" in result.output

        result = self.run(["config", "invalid-image.foo=1"])
        assert result.exit_code == 1
        assert "foo is not a valid option for check invalid-image" in result.output

        result = self.run(["config", "invalid-image.enabled=foo"])
        assert result.exit_code == 1
        assert "invalid-image.enabled must be true or false" in result.output

        result = self.run(["config", "cover-dimensions.squareness=foo"])
        assert result.exit_code == 1
        assert "cover-dimensions.squareness must be a non-negative floating point number" in result.output

        result = self.run(["config", "cover-dimensions.min_pixels=99.9"])
        assert result.exit_code == 1
        assert "cover-dimensions.min_pixels must be a non-negative integer" in result.output

    def test_config_export(self):
        path = TestCliConfig.library / "export.json"
        result = self.run(["config", "--export", str(path)], init=True)
        assert result.exit_code == 0
        assert "wrote" in result.output

        obj = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(obj, dict)
        assert obj["settings.library"] == str(TestCliConfig.library)

    def test_config_import(self):
        result = self.run(["config", "settings.rescan"], init=True)
        assert "settings.rescan = auto" in result.output

        path = TestCliConfig.library / "import.json"
        path.write_text(json.dumps({"settings.rescan": "never"}))

        result = self.run(["config", "--import", str(path)])
        assert result.exit_code == 0
        assert "imported" in result.output

        result = self.run(["config", "settings.rescan"])
        assert "settings.rescan = never" in result.output

    def test_config_reset(self):
        result = self.run(["config", "settings.tagger=mp3tag"], init=True)
        assert "settings.tagger = mp3tag" in result.output  # non-default setting

        result = self.run(["config", "settings.library"])
        assert f"settings.library = {str(TestCliConfig.library)}" in result.output
        result = self.run(["config", "settings.tagger"])
        assert "settings.tagger = mp3tag" in result.output

        result = self.run(["config", "--reset"])
        assert "reset to default except for library directory" in result.output

        result = self.run(["config", "settings.library"], init=True)
        assert f"settings.library = {str(TestCliConfig.library)}" in result.output  # not reset
        result = self.run(["config", "settings.tagger"])
        assert f"settings.tagger = {os.linesep}" in result.output  # reset
