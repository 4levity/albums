import contextlib
import os
from typing import List, Tuple

import rich
from rich.console import RenderableType

from albums.app import Context
from albums.database import connection, operations
from albums.interactive.interact import OPTION_IGNORE_CHECK, interact
from albums.types import Album, CheckResult, Fixer, ProblemCategory, Stream, Track


class MockFixer(Fixer):
    def __init__(self, ctx: Context, album: Album):
        table: Tuple[List[str], List[List[RenderableType]]] = (["track", "title"], [["1", "one"]])
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
        album = Album(os.sep, [Track("1.flac")])
        ctx = Context()
        fixer = MockFixer(ctx, album)
        mock_choice = mocker.patch("albums.interactive.interact.choice", return_value=fixer.options[0])

        (changed, quit) = interact(ctx, "", CheckResult(ProblemCategory.TAGS, "hello", fixer), album)
        assert changed
        assert not quit
        assert mock_choice.call_count == 1

    def test_fix_ignore_check(self, mocker):
        album = Album(os.sep, [Track("1.flac", stream=Stream())], album_id=1)
        ctx = Context()
        with contextlib.closing(connection.open(connection.MEMORY)) as ctx.db:
            album_id = operations.add(ctx.db, album)

            fixer = MockFixer(ctx, album)
            mock_choice = mocker.patch("albums.interactive.interact.choice", return_value=OPTION_IGNORE_CHECK)
            mock_ask = mocker.patch.object(rich.prompt.Confirm, "ask", return_value=True)

            (changed, quit) = interact(ctx, "album-tag", CheckResult(ProblemCategory.TAGS, "hello", fixer), album)
            assert not changed
            assert quit
            assert mock_choice.call_count == 1
            assert mock_ask.call_count == 1
            assert mock_ask.call_args.args[0] == ('Do you want to ignore the check "album-tag" for this album in the future?')

            rows = ctx.db.execute("SELECT COUNT(*) FROM album_ignore_check WHERE album_id = ?", (album_id,)).fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 1
