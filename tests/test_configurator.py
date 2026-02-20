import contextlib

from albums.app import Context
from albums.database import configuration, connection
from albums.interactive.configurator import interactive_config


class TestConfigurator:
    def test_configurator_start(self, mocker):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            mock_choice = mocker.patch("albums.interactive.configurator.choice", return_value="exit")
            interactive_config(Context(), db)
            assert mock_choice.call_count == 1

    def test_enable_disable_checks(self, mocker):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            mock_choice = mocker.patch("albums.interactive.configurator.choice")
            mock_choice.side_effect = ["enable", "exit"]

            request_enabled_checks = ["required-tags", "invalid-image"]

            class DialogRun:
                def run(self):
                    return request_enabled_checks

            mock_checklist = mocker.patch("albums.interactive.configurator.checkboxlist_dialog", return_value=DialogRun())

            interactive_config(Context(), db)

            assert mock_choice.call_count == 2
            assert mock_checklist.call_count == 1
            config = configuration.load(db)
            config_enabled_checks = [check_name for check_name, check_config in config.checks.items() if check_config["enabled"]]
            assert config_enabled_checks == request_enabled_checks

    # TODO test settings, check configs
