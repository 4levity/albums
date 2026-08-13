from unittest.mock import call

from sqlalchemy import select
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.path.check_unreadable_track import CheckUnreadableTrack
from albums.database import connection
from albums.entities import Album, Track
from albums.library import scanner

from ...fixtures.create_library import create_library


class TestCheckUnreadable:
    def test_check_unreadable_track(self, mocker):
        album = Album(path="foo", tracks=[Track(filename="1.mp3")])
        ctx = Context()
        ctx.config.library = create_library("unreadable_track", [album])
        with open(ctx.config.library / album.path / "2.mp3", "wb") as f:
            f.write(b"not a valid mp3")
        ctx.db = connection.db_open(connection.MEMORY)
        with Session(ctx.db) as session:
            scanner.scan(ctx, session)
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
            assert fix_result
            assert mock_rename.call_args_list == [
                call(ctx.config.library / album.path / "2.mp3", ctx.config.library / album.path / "2.mp3.unreadable")
            ]
