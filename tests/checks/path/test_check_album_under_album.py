import os

from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.path.check_album_under_album import CheckAlbumUnderAlbum
from albums.database import MEMORY, db_open
from albums.entities import Album, Track


class TestCheckAlbumUnderAlbum:
    def test_album_under_album(self):
        albums = [
            Album(path=f"foo{os.sep}bar{os.sep}", tracks=[Track(filename="1.flac")]),
            Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")]),
            Album(path="foobar" + os.sep, tracks=[Track(filename="1.flac")]),
        ]

        ctx = Context()
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                checker = CheckAlbumUnderAlbum(ctx, session=session)
                session.add(albums[0])
                session.add(albums[1])
                session.add(albums[2])
                session.flush()

                result = checker.check(albums[1])
                assert "there is 1 album in a directory under album foo" in result.message

                result = checker.check(albums[0])
                assert result is None
        finally:
            ctx.db.dispose()

    def test_album_under_album_multiple(self):
        albums = [
            Album(path=f"foo{os.sep}bar{os.sep}", tracks=[Track(filename="1.flac")]),
            Album(path=f"foo{os.sep}baz{os.sep}", tracks=[Track(filename="1.flac")]),
            Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")]),
        ]

        ctx = Context()
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                checker = CheckAlbumUnderAlbum(ctx, session=session)
                session.add(albums[0])
                session.add(albums[1])
                session.add(albums[2])
                session.flush()

                result = checker.check(albums[2])
                assert "there are 2 albums in directories under album foo" in result.message

                result = checker.check(albums[0])
                assert result is None
        finally:
            ctx.db.dispose()
