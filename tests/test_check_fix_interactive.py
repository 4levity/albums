import rich
from albums import app
from albums.checks.base_fixer import Fixer, FixerInteractivePrompt
from albums.types import Album, Track


class MockFixer(Fixer):
    def __init__(self, ctx: app.Context, album: Album):
        super(MockFixer, self).__init__("album_tag", ctx, album, True, True)

    def get_interactive_prompt(self):
        return FixerInteractivePrompt("message", "question?", ["A", "B"], (["track", "title"], [["1", "one"]]), True, True)

    def fix_interactive(self, option):
        return True

    def fix_automatic(self):
        return True


class TestCheckFixInteractive:
    def test_fix_interactive(self, mocker):
        album = Album("/", [Track("1.flac")])
        ctx = app.Context()
        fixer = MockFixer(ctx, album)
        mock_TerminalMenu = mocker.patch("albums.checks.base_fixer.TerminalMenu")
        mock_menu = mock_TerminalMenu.return_value
        mock_menu.show.return_value = 0
        mock_ask = mocker.patch.object(rich.prompt.Confirm, "ask", return_value=True)

        assert fixer.interact()
        assert mock_menu.show.call_count == 1
        assert mock_ask.call_count == 1
        assert mock_ask.call_args.args[0] == ('Selected "A" - are you sure?')

    def test_fix_ignore_check(self, mocker):
        album = Album("/", [Track("1.flac")])
        ctx = app.Context()
        ctx.db = mocker.Mock()
        ctx.db.execute.return_value = None
        ctx.db.commit.return_value = None
        fixer = MockFixer(ctx, album)
        mock_TerminalMenu = mocker.patch("albums.checks.base_fixer.TerminalMenu")
        mock_menu = mock_TerminalMenu.return_value
        mock_menu.show.return_value = None
        mock_ask = mocker.patch.object(rich.prompt.Confirm, "ask", return_value=True)

        assert not fixer.interact()
        assert mock_menu.show.call_count == 1
        assert mock_ask.call_count == 1
        assert mock_ask.call_args.args[0] == ('Do you want to ignore the check "album_tag" for this album in the future?')
        assert ctx.db.execute.call_count == 2
        assert ctx.db.execute.call_args.args[0] == "INSERT INTO album_ignore_check (album_id, check_name) VALUES (?, ?);"
