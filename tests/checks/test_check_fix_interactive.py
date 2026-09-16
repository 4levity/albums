import io
import os
from typing import Sequence, Tuple

from rich.console import Console, RenderableType
from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.database import MEMORY, db_open
from albums.entities import Album, Track
from albums.interactive.interact import OPTION_IGNORE_CHECK, OPTION_MORE_OPTIONS, interact


class MockFixer(Fixer):
    def __init__(self, ctx: Context, album: Album, options=["A", "B"], option_free_text=True, option_automatic_index: int | None = 0):
        table: Tuple[Sequence[str], Sequence[Sequence[RenderableType]]] = (["track", "title"], [["1", "one"]])
        super(MockFixer, self).__init__(
            lambda option: self._fix(album, option), options, option_free_text, option_automatic_index, table, "which one"
        )

    def _fix(self, album, option):
        return FixResult.CHANGED_ALBUM


class TestCheckFixInteractive:
    def test_fix_interactive(self, mocker):
        album = Album(path=os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.db = db_open(MEMORY)
        fixer = MockFixer(ctx, album)
        mock_choice = mocker.patch("albums.interactive.interact.choice", return_value=fixer.options[0])

        with Session(ctx.db) as session:
            (changed, deleted, quit) = interact(ctx, session, "", CheckResult("hello", fixer), album, True)
            assert changed
            assert not deleted
            assert not quit
            assert mock_choice.call_count == 1

    def test_fix_ignore_check(self, mocker):
        album = Album(path=os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                session.add(album)
                session.flush()

                fixer = MockFixer(ctx, album)
                mocker.patch("albums.interactive.interact.choice").side_effect = [OPTION_MORE_OPTIONS, OPTION_IGNORE_CHECK]
                mock_confirm = mocker.patch("albums.interactive.interact.confirm", return_value=True)

                (changed, deleted, quit) = interact(ctx, session, "album", CheckResult("hello", fixer), album, True)
                assert changed
                assert quit
                assert mock_confirm.call_count == 1
                assert mock_confirm.call_args.args[0] == ('Do you want to ignore the check "album" for this album?')

                rows = session.scalar(text("SELECT COUNT(*) FROM album_ignore_check WHERE album_id = :id"), {"id": album.album_id})
                assert rows == 1
        finally:
            ctx.db.dispose()

    def test_fix_ignore_check_shows_implicit_ignores(self, mocker):
        album = Album(path=os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.db = db_open(MEMORY)
        buffer = io.StringIO()
        ctx.console = Console(file=buffer, width=200)  # wide enough that messages are not wrapped
        try:
            with Session(ctx.db) as session:
                session.add(album)
                session.flush()

                fixer = MockFixer(ctx, album)
                mocker.patch("albums.interactive.interact.choice").side_effect = [OPTION_MORE_OPTIONS, OPTION_IGNORE_CHECK]
                mock_confirm = mocker.patch("albums.interactive.interact.confirm", return_value=True)

                interact(ctx, session, "disc-in-track-number", CheckResult("hello", fixer), album, True)

            output = buffer.getvalue()
            assert 'Ignoring check "disc-in-track-number" will also implicitly ignore these checks for this album:' in output
            # the implicitly ignored checks are listed as bullets in the order the checks would run
            positions = [
                output.index(f"- {name}")
                for name in ("invalid-track-or-disc-number", "disc-numbering", "track-numbering", "zero-pad-numbers", "track-filename")
            ]
            assert positions == sorted(positions)
            assert mock_confirm.call_count == 1
        finally:
            ctx.db.dispose()

    def test_fix_ignore_check_already_implicitly_ignored(self, mocker):
        album = Album(path=os.sep, tracks=[Track(filename="1.flac")])
        album.ignore_checks.append("disc-in-track-number")
        ctx = Context()
        ctx.db = db_open(MEMORY)
        buffer = io.StringIO()
        ctx.console = Console(file=buffer, width=200)  # wide enough that messages are not wrapped
        try:
            with Session(ctx.db) as session:
                session.add(album)
                session.flush()

                fixer = MockFixer(ctx, album)
                mocker.patch("albums.interactive.interact.choice").side_effect = [OPTION_MORE_OPTIONS, OPTION_IGNORE_CHECK]
                mock_confirm = mocker.patch("albums.interactive.interact.confirm", return_value=True)

                (changed, deleted, quit) = interact(ctx, session, "invalid-track-or-disc-number", CheckResult("hello", fixer), album, True)
                # the check is (implicitly) ignored, so the prompt reports it as ignored and does not confirm or add a row
                assert changed
                assert quit
                assert not deleted
                assert mock_confirm.call_count == 0
                rows = session.scalar(text("SELECT COUNT(*) FROM album_ignore_check WHERE album_id = :id"), {"id": album.album_id})
                assert rows == 1

            output = buffer.getvalue()
            assert (
                'cannot ignore check "invalid-track-or-disc-number" for this album: it is already implicitly ignored '
                'because it depends on ignored check "disc-in-track-number"' in output
            )
        finally:
            ctx.db.dispose()

    def test_fix_ignore_check_no_options(self, mocker):
        album = Album(path=os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        # only on Python 3.14.2, only when tests run with pytest-cov, this line causes ResourceWarning: unclosed database although it's closed below?
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                session.add(album)
                session.flush()
                fixer = MockFixer(ctx, album, [], False, None)
                mocker.patch("albums.interactive.interact.choice").side_effect = [OPTION_MORE_OPTIONS, OPTION_IGNORE_CHECK]
                mock_confirm = mocker.patch("albums.interactive.interact.confirm", return_value=True)

                (changed, deleted, quit) = interact(ctx, session, "album", CheckResult("hello", fixer), album, True)
                assert mock_confirm.call_count == 1
                assert mock_confirm.call_args.args[0] == ('Do you want to ignore the check "album" for this album?')

                rows = session.scalar(text("SELECT COUNT(*) FROM album_ignore_check WHERE album_id = :id"), {"id": album.album_id})
                assert rows == 1
        finally:
            ctx.db.dispose()
