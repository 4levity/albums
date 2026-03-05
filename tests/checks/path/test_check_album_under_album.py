import os

from albums.app import Context
from albums.checks.path.check_album_under_album import CheckAlbumUnderAlbum
from albums.database import connection, operations
from albums.tagger.types import StreamInfo
from albums.types import Album, Track


class TestCheckAlbumUnderAlbum:
    def test_album_under_album(self):
        def track(filename):
            return Track(filename, {}, 1, 0, StreamInfo(1.5))

        albums = [
            Album(f"foo{os.sep}bar{os.sep}", [track("1.flac")]),
            Album("foo" + os.sep, [track("1.flac")]),
            Album("foobar" + os.sep, [track("1.flac")]),
        ]

        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
        try:
            checker = CheckAlbumUnderAlbum(ctx)

            operations.add(ctx.db, albums[0])
            operations.add(ctx.db, albums[1])
            operations.add(ctx.db, albums[2])

            result = checker.check(albums[1])
            assert "there are 1 albums in directories under album foo" in result.message

            result = checker.check(albums[0])
            assert result is None
        finally:
            ctx.db.dispose()
