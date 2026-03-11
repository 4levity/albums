import os

from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.path.check_album_under_album import CheckAlbumUnderAlbum
from albums.database import connection
from albums.database.models import AlbumEntity, TrackEntity


class TestCheckAlbumUnderAlbum:
    def test_album_under_album(self):
        albums = [
            AlbumEntity(path=f"foo{os.sep}bar{os.sep}", tracks=[TrackEntity(filename="1.flac")]),
            AlbumEntity(path="foo" + os.sep, tracks=[TrackEntity(filename="1.flac")]),
            AlbumEntity(path="foobar" + os.sep, tracks=[TrackEntity(filename="1.flac")]),
        ]

        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
        try:
            checker = CheckAlbumUnderAlbum(ctx)
            with Session(ctx.db) as session:
                session.add(albums[0])
                session.add(albums[1])
                session.add(albums[2])
                session.flush()

                result = checker.check(albums[1])
                assert "there are 1 albums in directories under album foo" in result.message

                result = checker.check(albums[0])
                assert result is None
        finally:
            ctx.db.dispose()
