import contextlib
import os
from typing import Sequence, Tuple

from rich.console import RenderableType

from albums.app import Context
from albums.database import connection, operations
from albums.interactive.interact import OPTION_IGNORE_CHECK, interact
from albums.tagger.types import StreamInfo
from albums.types import Album, CheckResult, Fixer, Track


class MockFixer(Fixer):
    def __init__(self, ctx: Context, album: Album, options=["A", "B"], option_free_text=True, option_automatic_index: int | None = 0):
        table: Tuple[Sequence[str], Sequence[Sequence[RenderableType]]] = (["track", "title"], [["1", "one"]])
        super(MockFixer, self).__init__(
            lambda option: self._fix(album, option), options, option_free_text, option_automatic_index, table, "which one"
        )

    def _fix(self, album, option) -> bool:
        return True


class TestCheckFixInteractive:
    def test_fix_interactive(self, mocker):
        album = Album(os.sep, [Track("1.flac")])
        ctx = Context()
        fixer = MockFixer(ctx, album)
        mock_choice = mocker.patch("albums.interactive.interact.shortcuts.choice", return_value=fixer.options[0])

        (changed, quit) = interact(ctx, "", CheckResult("hello", fixer), album, True)
        assert changed
        assert not quit
        assert mock_choice.call_count == 1

    def test_fix_ignore_check(self, mocker):
        album = Album(os.sep, [Track("1.flac", stream=StreamInfo())], album_id=1)
        ctx = Context()
        with contextlib.closing(connection.open(connection.MEMORY)) as ctx.db:
            album_id = operations.add(ctx.db, album)

            fixer = MockFixer(ctx, album)
            mock_choice = mocker.patch("albums.interactive.interact.shortcuts.choice", return_value=OPTION_IGNORE_CHECK)
            mock_confirm = mocker.patch("albums.interactive.interact.shortcuts.confirm", return_value=True)

            (changed, quit) = interact(ctx, "album-tag", CheckResult("hello", fixer), album, True)
            assert changed
            assert quit
            assert mock_choice.call_count == 1
            assert mock_confirm.call_count == 1
            assert mock_confirm.call_args.args[0] == ('Do you want to ignore the check "album-tag" for this album?')

            rows = ctx.db.execute("SELECT COUNT(*) FROM album_ignore_check WHERE album_id = ?", (album_id,)).fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 1

    def test_fix_ignore_check_no_options(self, mocker):
        album = Album(os.sep, [Track("1.flac", stream=StreamInfo())], album_id=1)
        ctx = Context()
        with contextlib.closing(connection.open(connection.MEMORY)) as ctx.db:
            album_id = operations.add(ctx.db, album)

            fixer = MockFixer(ctx, album, [], False, None)
            mocker.patch("albums.interactive.interact.shortcuts.choice", return_value=OPTION_IGNORE_CHECK)
            mock_confirm = mocker.patch("albums.interactive.interact.shortcuts.confirm", return_value=True)

            (changed, quit) = interact(ctx, "album-tag", CheckResult("hello", fixer), album, True)
            assert mock_confirm.call_count == 1
            assert mock_confirm.call_args.args[0] == ('Do you want to ignore the check "album-tag" for this album?')

            rows = ctx.db.execute("SELECT COUNT(*) FROM album_ignore_check WHERE album_id = ?", (album_id,)).fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 1
