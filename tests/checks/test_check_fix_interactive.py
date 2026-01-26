import rich
from albums import app
from albums.checks.base_check import CheckResult, Fixer, ProblemCategory
from albums.types import Album, Track
from albums.checks.interact import interact


class MockFixer(Fixer):
    def __init__(self, ctx: app.Context, album: Album):
        table = (["track", "title"], [["1", "one"]])
        options = ["A", "B"]
        option_free_text = True
        option_automatic_index = 0
        super(MockFixer, self).__init__(
            lambda option: self._fix(album, option), options, option_free_text, option_automatic_index, table, "which one"
        )

    def _fix(self, album, option) -> bool:
        return True


class TestCheckFixInteractive:
    def test_fix_interactive(self, mocker):
        album = Album("/", [Track("1.flac")])
        ctx = app.Context()
        fixer = MockFixer(ctx, album)
        mock_TerminalMenu = mocker.patch("albums.checks.interact.TerminalMenu")
        mock_menu = mock_TerminalMenu.return_value
        mock_menu.show.return_value = 0
        mock_ask = mocker.patch.object(rich.prompt.Confirm, "ask", return_value=True)

        assert interact(ctx, "", CheckResult(ProblemCategory.TAGS, "hello", fixer), album)
        assert mock_menu.show.call_count == 1
        assert mock_ask.call_count == 1
        assert mock_ask.call_args.args[0] == ('Selected "A" - are you sure?')

    def test_fix_ignore_check(self, mocker):
        album = Album("/", [Track("1.flac")], album_id=1)
        ctx = app.Context()
        ctx.db = mocker.Mock()
        ctx.db.execute.return_value = None
        ctx.db.commit.return_value = None
        fixer = MockFixer(ctx, album)
        mock_TerminalMenu = mocker.patch("albums.checks.interact.TerminalMenu")
        mock_menu = mock_TerminalMenu.return_value
        mock_menu.show.return_value = 3  # fixer has 2 options + free text, next option is ignore check
        mock_ask = mocker.patch.object(rich.prompt.Confirm, "ask", return_value=True)

        assert not interact(ctx, "album_tag", CheckResult(ProblemCategory.TAGS, "hello", fixer), album)
        assert mock_menu.show.call_count == 1
        assert mock_ask.call_count == 1
        assert mock_ask.call_args.args[0] == ('Do you want to ignore the check "album_tag" for this album in the future?')
        assert ctx.db.execute.call_count == 2
        assert ctx.db.execute.call_args.args[0] == "INSERT INTO album_ignore_check (album_id, check_name) VALUES (?, ?);"
