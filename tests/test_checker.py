import os

import pytest
from rich.text import Text
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.checker import Checker
from albums.database import connection, selector
from albums.database.models import AlbumEntity, TrackEntity, TrackTagEntity
from albums.library import scanner
from albums.types import BasicTag

from .fixtures.create_library import create_library


class TestChecker:
    def test_run_enabled_all_ok(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="01 one.flac",
                    tags=[
                        TrackTagEntity(tag=BasicTag.ARTIST, value="A"),
                        TrackTagEntity(tag=BasicTag.ALBUM, value="Foo"),
                        TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="01"),
                        TrackTagEntity(tag=BasicTag.TITLE, value="one"),
                    ],
                ),
                TrackEntity(
                    filename="02 two.flac",
                    tags=[
                        TrackTagEntity(tag=BasicTag.ARTIST, value="A"),
                        TrackTagEntity(tag=BasicTag.ALBUM, value="Foo"),
                        TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="02"),
                        TrackTagEntity(tag=BasicTag.TITLE, value="two"),
                    ],
                ),
                TrackEntity(
                    filename="03 three.flac",
                    tags=[
                        TrackTagEntity(tag=BasicTag.ARTIST, value="A"),
                        TrackTagEntity(tag=BasicTag.ALBUM, value="Foo"),
                        TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="03"),
                        TrackTagEntity(tag=BasicTag.TITLE, value="three"),
                    ],
                ),
            ],
        )
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
        ctx.select_album_entities = lambda session: selector.load_album_entities(session)
        try:
            with Session(ctx.db) as session:
                session.add(album)
                session.commit()
            showed_issues = Checker(ctx, automatic=False, preview=False, fix=False, interactive=False, show_ignore_option=False).run_enabled()
            assert showed_issues == 0
        finally:
            ctx.db.dispose()

    def test_run_enabled_automatic_dependent_check_ok(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1-01 one.flac",
                    tags=[
                        TrackTagEntity(tag=BasicTag.ARTIST, value="A"),
                        TrackTagEntity(tag=BasicTag.ALBUM, value="Foo"),
                        TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1-01"),
                        TrackTagEntity(tag=BasicTag.TITLE, value="one"),
                    ],
                )
            ],
        )
        ctx = Context()
        ctx.config.library = create_library("checker_automatic", [album])
        ctx.db = connection.open(connection.MEMORY, True)
        try:
            with Session(ctx.db) as session:
                ctx.select_album_entities = lambda s: selector.load_album_entities(s)
                scanner.scan(ctx, session)
                session.commit()

            showed_issues = Checker(ctx, automatic=True, preview=False, fix=False, interactive=False, show_ignore_option=False).run_enabled()

            # there is only 1 issue "disc-in-tracknumber" and if "invalid-track-or-disc-number" check sees the FIXED album it will report no problem
            assert showed_issues == 1

            with Session(ctx.db) as session:
                album = next(ctx.select_album_entities(session))
                assert album.tracks[0].get(BasicTag.TRACKNUMBER) == ("01",)
                assert album.tracks[0].get(BasicTag.DISCNUMBER) == ("1",)
        finally:
            ctx.db.dispose()

    def test_run_enabled_dependent_check_failures(self, mocker):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[  # disc-in-track-number fails -> invalid-track-or-disc-number does not run -> other checks do not run
                TrackEntity(
                    filename="1.flac",
                    tags=[
                        TrackTagEntity(tag=BasicTag.ALBUM, value="Foo"),
                        TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1-01"),
                        TrackTagEntity(tag=BasicTag.TITLE, value="one"),
                    ],
                ),
                TrackEntity(
                    filename="2.flac",
                    tags=[
                        TrackTagEntity(tag=BasicTag.ALBUM, value="Foo"),
                        TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1-02"),
                        TrackTagEntity(tag=BasicTag.TITLE, value="two"),
                    ],
                ),
                TrackEntity(
                    filename="3.flac",
                    tags=[
                        TrackTagEntity(tag=BasicTag.ALBUM, value="Foo"),
                        TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1-03"),
                        TrackTagEntity(tag=BasicTag.TITLE, value="three"),
                    ],
                ),
            ],
        )
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
        ctx.select_album_entities = lambda session: selector.load_album_entities(session)
        try:
            with Session(ctx.db) as session:
                session.add(album)
                session.commit()

            print_spy = mocker.spy(ctx.console, "print")
            Checker(ctx, automatic=False, preview=False, fix=False, interactive=False, show_ignore_option=False).run_enabled()
            output = " ".join((Text.from_markup(call_args.args[0]).plain for call_args in print_spy.call_args_list))
            assert f'track numbers formatted as number-dash-number, probably discnumber and tracknumber : "foo{os.sep}"' in output
            assert f'dependency not met for check invalid-track-or-disc-number on "foo{os.sep}": disc-in-track-number must pass first' in output
            assert f'dependency not met for check disc-numbering on "foo{os.sep}": invalid-track-or-disc-number must pass first' in output
        finally:
            ctx.db.dispose()

    def test_run_invalid_config(self, mocker):
        ctx = Context()
        checks = dict(ctx.config.checks)
        checks["invalid-track-or-disc-number"] = {"enabled": False}
        ctx.config.checks = checks
        print_spy = mocker.spy(ctx.console, "print")
        with pytest.raises(SystemExit):
            Checker(ctx, automatic=False, preview=False, fix=False, interactive=False, show_ignore_option=False).run_enabled()
        output = " ".join((Text.from_markup(call_args.args[0]).plain for call_args in print_spy.call_args_list))
        assert "Configuration error" in output
        assert "invalid-track-or-disc-number required by" in output
