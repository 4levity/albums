from unittest.mock import call

from sqlalchemy import select
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.check_types import Fixer, FixResult
from albums.checks.path.check_unreadable_track import CheckUnreadableTrack
from albums.database import MEMORY, db_open
from albums.entities import Album, Track
from albums.library import run_scan

from ...fixtures.create_library import create_library


def table_rows(fixer: Fixer) -> list[list[str]]:
    table = fixer.get_table()
    assert table is not None
    return [[str(cell) for cell in row] for row in table[1]]


class TestCheckUnreadable:
    def test_check_unreadable_track(self, mocker):
        album = Album(path="foo", tracks=[Track(filename="1.mp3")])
        ctx = Context()
        ctx.config.library = create_library("unreadable_track", [album])
        with open(ctx.config.library / album.path / "2.mp3", "wb") as f:
            f.write(b"not a valid mp3")
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            run_scan(ctx, session)
            [(album,)] = session.execute(select(Album)).tuples()
            result = CheckUnreadableTrack(ctx).check(album)
            assert result is not None
            assert result.message == "1 unreadable track, example 2.mp3"
            assert result.fixer is not None
            assert result.fixer.get_table()
            assert result.fixer.option_automatic_index is None
            assert result.fixer.options == [">> Rename unreadable tracks to <filename>.unreadable"]

            mock_rename = mocker.patch("albums.checks.path.check_unreadable_track.rename")
            fix_result = result.fixer.fix(result.fixer.options[0])
            assert fix_result == FixResult.CHANGED_ALBUM
            assert mock_rename.call_args_list == [
                call(ctx.config.library / album.path / "2.mp3", ctx.config.library / album.path / "2.mp3.unreadable")
            ]

    def test_check_unreadable_track_collision(self, mocker):
        album = Album(path="foo", tracks=[Track(filename="1.mp3")])
        ctx = Context()
        ctx.config.library = create_library("unreadable_track_collision", [album])
        album_path = ctx.config.library / album.path
        with open(album_path / "2.mp3", "wb") as f:
            f.write(b"not a valid mp3")
        # a file already exists at the name the track would be renamed to
        with open(album_path / "2.mp3.unreadable", "wb") as f:
            f.write(b"existing file")
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            run_scan(ctx, session)
            [(album,)] = session.execute(select(Album)).tuples()
            result = CheckUnreadableTrack(ctx).check(album)
            assert result is not None
            assert result.message == "1 unreadable track, example 2.mp3"
            assert result.fixer is not None
            row = next(r for r in table_rows(result.fixer) if r[0] == "2.mp3")
            assert row[2] == "[yellow]2.mp3.unreadable.1[/yellow]"

            mock_rename = mocker.patch("albums.checks.path.check_unreadable_track.rename")
            fix_result = result.fixer.fix(result.fixer.options[0])
            assert fix_result == FixResult.CHANGED_ALBUM
            assert mock_rename.call_args_list == [call(album_path / "2.mp3", album_path / "2.mp3.unreadable.1")]

    def test_fix_unreadable_track_late_collision(self, mocker):
        album = Album(path="foo", tracks=[Track(filename="1.mp3")])
        ctx = Context()
        ctx.config.library = create_library("unreadable_track_late_collision", [album])
        album_path = ctx.config.library / album.path
        with open(album_path / "2.mp3", "wb") as f:
            f.write(b"not a valid mp3")
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            run_scan(ctx, session)
            [(album,)] = session.execute(select(Album)).tuples()
            result = CheckUnreadableTrack(ctx).check(album)
            assert result is not None
            assert result.fixer is not None
            row = next(r for r in table_rows(result.fixer) if r[0] == "2.mp3")
            assert row[2] == "[yellow]2.mp3.unreadable[/yellow]"

            # a colliding file appears after the check but before the fix
            with open(album_path / "2.mp3.unreadable", "wb") as f:
                f.write(b"existing file")
            mock_rename = mocker.patch("albums.checks.path.check_unreadable_track.rename")
            fix_result = result.fixer.fix(result.fixer.options[0])
            assert fix_result == FixResult.CHANGED_ALBUM
            assert mock_rename.call_args_list == [call(album_path / "2.mp3", album_path / "2.mp3.unreadable.1")]
