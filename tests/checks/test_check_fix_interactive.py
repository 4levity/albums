import rich

from albums import app
from albums.checks.base_check import CheckResult, Fixer, ProblemCategory
from albums.checks.interact import interact
from albums.database import connection, operations
from albums.types import Album, Stream, Track


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
        mock_TerminalMenu = mocker.patch("albums.checks.interact.simple_term_menu.TerminalMenu")
        mock_menu = mock_TerminalMenu.return_value
        mock_menu.show.return_value = 0

        (changed, quit) = interact(ctx, "", CheckResult(ProblemCategory.TAGS, "hello", fixer), album)
        assert changed
        assert not quit
        assert mock_menu.show.call_count == 1

    def test_fix_ignore_check(self, mocker):
        album = Album("/", [Track("1.flac", stream=Stream())], album_id=1)
        ctx = app.Context()
        ctx.db = connection.open(connection.MEMORY)
        album_id = operations.add(ctx.db, album)

        fixer = MockFixer(ctx, album)
        mock_TerminalMenu = mocker.patch("albums.checks.interact.simple_term_menu.TerminalMenu")
        mock_menu = mock_TerminalMenu.return_value
        mock_menu.show.return_value = 3  # fixer has 2 options + free text, next option is ignore check
        mock_ask = mocker.patch.object(rich.prompt.Confirm, "ask", return_value=True)

        (changed, quit) = interact(ctx, "album_tag", CheckResult(ProblemCategory.TAGS, "hello", fixer), album)
        assert not changed
        assert quit
        assert mock_menu.show.call_count == 1
        assert mock_ask.call_count == 1
        assert mock_ask.call_args.args[0] == ('Do you want to ignore the check "album_tag" for this album in the future?')

        rows = ctx.db.execute("SELECT COUNT(*) FROM album_ignore_check WHERE album_id = ?", (album_id,)).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 1
        ctx.db.close()
