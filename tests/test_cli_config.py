import re

import pytest

from . import helpers
from .fixtures.create_library import create_library


class TestCliConfig:
    @pytest.fixture(scope="function", autouse=True)
    def setup_cli_tests(self):
        TestCliConfig.library = create_library("cli_cfg", [])

    def run(self, params: list[str], init=False):
        return helpers.run(params, TestCliConfig.library, init)

    def test_config(self):
        def assert_setting(output: str, name: str, value: str):
            assert re.search(f"│ {re.escape(name)}\\s+│ {re.escape(value)}", output)

        result = self.run(["config", "--show"], init=True)
        assert_setting(result.output, "settings.library", str(TestCliConfig.library)[:16])
        assert_setting(result.output, "settings.rescan", "auto")
        # assert_setting(result.output, "settings.tagger", "easytag")  # only if it is installed
        assert_setting(result.output, "settings.open_folder_command", " ")
        assert_setting(result.output, "cover_dimensions.min_pixels", "100")
        assert_setting(result.output, "cover_dimensions.squareness", "0.98")
        assert_setting(result.output, "required_tags.enabled", "False")

        result = self.run(["config", "settings.library", "."])
        assert result.exit_code == 0
        assert "settings.library = ." in result.output
        result = self.run(["config", "settings.rescan", "never"])
        assert "settings.rescan = never" in result.output
        result = self.run(["config", "settings.tagger", "mp3tag"])
        assert "settings.tagger = mp3tag" in result.output
        result = self.run(["config", "settings.open_folder_command", "xdg-open"])
        assert "settings.open_folder_command = xdg-open" in result.output

        result = self.run(["config", "cover_dimensions.min_pixels", "42"])
        assert "cover_dimensions.min_pixels = 42" in result.output
        result = self.run(["config", "cover_dimensions.squareness", "0.42"])
        assert "cover_dimensions.squareness = 0.42" in result.output
        result = self.run(["config", "required_tags.enabled", "True"])
        assert "required_tags.enabled = True" in result.output

        result = self.run(["config", "--show"])
        assert_setting(result.output, "settings.library", ".")
        assert_setting(result.output, "settings.rescan", "never")
        assert_setting(result.output, "settings.tagger", "mp3tag")
        assert_setting(result.output, "settings.open_folder_command", "xdg-open")
        assert_setting(result.output, "cover_dimensions.min_pixels", "42")
        assert_setting(result.output, "cover_dimensions.squareness", "0.42")
        assert_setting(result.output, "required_tags.enabled", "True")
        self.run(["config", "settings.library", str(TestCliConfig.library)])

    def test_config_invalid(self):
        result = self.run(["config", "settings.library"], init=True)
        assert result.exit_code == 1
        assert "both name and value" in result.output

        result = self.run(["config", "settings.foo", "bar"])
        assert result.exit_code == 1
        assert "not a valid setting" in result.output

        result = self.run(["config", "library", "."])
        assert result.exit_code == 1
        assert "invalid setting" in result.output

        result = self.run(["config", "foo.enabled", "true"])
        assert result.exit_code == 1
        assert "foo is not a valid check name" in result.output

        result = self.run(["config", "invalid_image.foo", "1"])
        assert result.exit_code == 1
        assert "foo is not a valid option for check invalid_image" in result.output

        result = self.run(["config", "invalid_image.enabled", "foo"])
        assert result.exit_code == 1
        assert "invalid_image.enabled must be true or false" in result.output

        result = self.run(["config", "cover_dimensions.squareness", "foo"])
        assert result.exit_code == 1
        assert "cover_dimensions.squareness must be a non-negative floating point number" in result.output

        result = self.run(["config", "cover_dimensions.min_pixels", "99.9"])
        assert result.exit_code == 1
        assert "cover_dimensions.min_pixels must be a non-negative integer" in result.output
