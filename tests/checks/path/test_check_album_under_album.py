import os

from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.path.check_album_under_album import CheckAlbumUnderAlbum
from albums.database import MEMORY, db_open
from albums.entities import Album, Track


def _albums(*paths):
    return [Album(path=path, tracks=[Track(filename="1.flac")]) for path in paths]


class TestCheckAlbumUnderAlbum:
    def _check_in_order(self, ctx, session, *albums):
        # checks run in path order, so feed the albums sorted
        checker = CheckAlbumUnderAlbum(ctx, session=session)
        for album in sorted(albums, key=lambda album: album.path):
            session.add(album)
        session.flush()
        return (checker.check(album) for album in sorted(albums, key=lambda album: album.path))

    def test_album_under_album(self):
        foo, foo_bar, foobar = _albums("foo" + os.sep, f"foo{os.sep}bar{os.sep}", "foobar" + os.sep)
        ctx = Context()
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                results = list(self._check_in_order(ctx, session, foo, foo_bar, foobar))
                assert results[0] is None
                assert results[1].message == f"in a directory under album foo{os.sep}"
                assert results[2] is None
        finally:
            ctx.db.dispose()

    def test_album_under_album_multiple(self):
        # foo/baz/ is not under the most recently checked album (foo/bar/), but the run of child
        # albums still started under foo/, so it fails against foo/
        foo, foo_bar, foo_baz = _albums("foo" + os.sep, f"foo{os.sep}bar{os.sep}", f"foo{os.sep}baz{os.sep}")
        ctx = Context()
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                results = list(self._check_in_order(ctx, session, foo, foo_bar, foo_baz))
                assert results[0] is None
                assert results[1].message == f"in a directory under album foo{os.sep}"
                assert results[2].message == f"in a directory under album foo{os.sep}"
        finally:
            ctx.db.dispose()

    def test_album_under_album_nested(self):
        a, a_b, a_b_c, a_c = _albums("a" + os.sep, f"a{os.sep}b{os.sep}", f"a{os.sep}b{os.sep}c{os.sep}", f"a{os.sep}c{os.sep}")
        ctx = Context()
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                results = list(self._check_in_order(ctx, session, a, a_b, a_b_c, a_c))
                assert results[0] is None
                assert results[1].message == f"in a directory under album a{os.sep}"
                assert results[2].message == f"in a directory under album a{os.sep}"
                # a/c/ is not under the most recently checked album (a/b/c/), but the run is still under a/
                assert results[3].message == f"in a directory under album a{os.sep}"
        finally:
            ctx.db.dispose()

    def test_album_under_album_case_sensitive(self):
        # paths that differ only in case are siblings, not parent/child: the check is case-sensitive
        albums = _albums(f"Casey{os.sep}Album (2001){os.sep}", f"CASEY{os.sep}ALBUM (2001){os.sep}Deep (2002){os.sep}")
        ctx = Context()
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                for result in self._check_in_order(ctx, session, *albums):
                    assert result is None
        finally:
            ctx.db.dispose()

    def test_album_under_album_wildcard_characters(self):
        # glob wildcard characters in paths must not affect the prefix test
        parent, child = _albums(f"100% Hits{os.sep}Vol_| 2{os.sep}", f"100% Hits{os.sep}Vol_| 2{os.sep}Bonus{os.sep}")
        ctx = Context()
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                results = list(self._check_in_order(ctx, session, parent, child))
                assert results[0] is None
                assert results[1].message == f"in a directory under album 100% Hits{os.sep}Vol_| 2{os.sep}"
        finally:
            ctx.db.dispose()

    def test_album_under_album_filtered_run(self):
        # a run without the parent album (e.g. filtered) cannot detect the child; that false negative is accepted
        child = _albums(f"foo{os.sep}bar{os.sep}")[0]
        ctx = Context()
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                (result,) = self._check_in_order(ctx, session, child)
                assert result is None
        finally:
            ctx.db.dispose()

    def test_album_under_album_rechecked(self):
        # a fix commits mid-run and re-runs all checks on the same album; the state must handle seeing
        # the same paths twice
        foo, foo_bar, foobar = _albums("foo" + os.sep, f"foo{os.sep}bar{os.sep}", "foobar" + os.sep)
        ctx = Context()
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                checker = CheckAlbumUnderAlbum(ctx, session=session)
                for album in (foo, foo_bar, foobar):
                    session.add(album)
                session.flush()
                assert checker.check(foo) is None
                assert checker.check(foo_bar) is not None
                assert checker.check(foobar) is None
                # re-run of the checks on the same albums
                assert checker.check(foo) is None
                assert checker.check(foo_bar) is not None
                assert checker.check(foobar) is None
        finally:
            ctx.db.dispose()

    def test_must_pass_checks(self):
        assert CheckAlbumUnderAlbum.must_pass_checks == {"duplicate-folder-name"}
