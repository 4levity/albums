import contextlib
import os

from albums.app import Context
from albums.checks.path.check_album_under_album import CheckAlbumUnderAlbum
from albums.database import connection, operations
from albums.types import Album, Stream, Track


class TestCheckAlbumUnderAlbum:
    def test_album_under_album(self):
        def track(filename):
            return Track(filename, {}, 1, 0, Stream(1.5))

        albums = [
            Album(f"foo{os.sep}bar{os.sep}", [track("1.flac")]),
            Album("foo" + os.sep, [track("1.flac")]),
            Album("foobar" + os.sep, [track("1.flac")]),
        ]

        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            ctx = Context()
            ctx.db = db
            checker = CheckAlbumUnderAlbum(ctx)

            operations.add(db, albums[0])
            operations.add(db, albums[1])
            operations.add(db, albums[2])

            result = checker.check(albums[1])
            assert "there are 1 albums in directories under album foo" in result.message

            result = checker.check(albums[0])
            assert result is None
