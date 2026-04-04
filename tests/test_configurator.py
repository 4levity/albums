import os
import platform

from albums.app import Context, Path
from albums.config import ID3v1Policy, PathCompatibilityOption, RescanOption
from albums.database import connection, db_config
from albums.interactive.configurator import interactive_config


class TestConfigurator:
    def test_configurator_start(self, mocker):
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
        try:
            mock_choice = mocker.patch("albums.interactive.configurator.choice", return_value="exit")
            interactive_config(ctx)
            assert mock_choice.call_count == 1
        finally:
            ctx.db.dispose()

    def test_settings(self, mocker):
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
        try:
            mocker.patch("albums.interactive.configurator.choice").side_effect = ["settings", "exit"]
            mock_choice = mocker.patch("albums.interactive.setup_settings.choice")
            mock_choice.side_effect = ["path_compatibility", "Linux", "rescan", "always", "id3v1", ID3v1Policy.CREATE, "back"]

            interactive_config(ctx)

            assert mock_choice.call_count == 7
            config = db_config.load(ctx.db)
            assert config.path_compatibility == PathCompatibilityOption.LINUX
            assert config.rescan == RescanOption.ALWAYS
            assert config.id3v1 == ID3v1Policy.CREATE
        finally:
            ctx.db.dispose()

    def test_enable_disable_checks(self, mocker):
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
        try:
            mock_choice = mocker.patch("albums.interactive.configurator.choice")
            mock_choice.side_effect = ["enable", "exit"]

            request_enabled_checks = ["cover-filename", "invalid-image"]

            class DialogRun:
                def run(self):
                    return request_enabled_checks

            mock_checklist = mocker.patch("albums.interactive.configurator.checkboxlist_dialog", return_value=DialogRun())

            interactive_config(ctx)

            assert mock_choice.call_count == 2
            assert mock_checklist.call_count == 1
            config = db_config.load(ctx.db)
            config_enabled_checks = set(check_name for check_name, check_config in config.checks.items() if check_config["enabled"])
            assert config_enabled_checks == set(request_enabled_checks)
        finally:
            ctx.db.dispose()

    def test_config_new_sync_dest(self, mocker):
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
        abs_path = "C:\\Music" if platform.system() == "Windows" else "/usr/share/music"
        try:
            mock_main_menu_choice = mocker.patch("albums.interactive.configurator.choice")
            mock_main_menu_choice.side_effect = ["destinations", "exit"]
            mock_destinations_choice = mocker.patch("albums.interactive.setup_destination.choice")
            mock_destinations_choice.side_effect = [
                "new",
                "",
                "relpath_template_artist",
                "relpath_template_compilation",
                "convert_profile",
                "save",
                "back",
            ]  # new destination, new collection, set template 1, set template 2, set conversion profile, save destination, back to main menu
            mock_prompt = mocker.patch("albums.interactive.setup_destination.prompt")
            template1 = f"$artist{os.sep}$album"
            template2 = f"Various{os.sep}$album"
            mock_prompt.side_effect = [
                abs_path,
                "test",
                template1,
                template2,
                "-b:a 320k mp3",
            ]  # destination path, collection name, relpath_template_artist, relpath_template_compilation, convert_profile

            interactive_config(ctx)

            assert mock_main_menu_choice.call_count == 2
            assert mock_destinations_choice.call_count == 7
            assert mock_prompt.call_count == 5
            config = db_config.load(ctx.db)
            assert len(config.sync_destinations) == 1
            dest = config.sync_destinations[0]
            assert dest.path_root == Path(abs_path)
            assert dest.collection == "test"
            assert dest.relpath_template_artist.template == template1
            assert dest.relpath_template_compilation.template == template2
            assert dest.convert_profile == "-b:a 320k mp3"
        finally:
            ctx.db.dispose()
