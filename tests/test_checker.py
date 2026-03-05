import os

import pytest
from rich.text import Text

from albums.app import Context
from albums.checks.checker import Checker
from albums.database import connection, selector
from albums.library import scanner
from albums.types import Album, BasicTag, Track

from .fixtures.create_library import create_library


class TestChecker:
    def test_run_enabled_all_ok(self):
        album = Album(
            "foo" + os.sep,
            [
                Track("01 one.flac", {BasicTag.ARTIST: ["A"], BasicTag.ALBUM: ["Foo"], BasicTag.TRACKNUMBER: ["01"], BasicTag.TITLE: ["one"]}),
                Track("02 two.flac", {BasicTag.ARTIST: ["A"], BasicTag.ALBUM: ["Foo"], BasicTag.TRACKNUMBER: ["02"], BasicTag.TITLE: ["two"]}),
                Track("03 three.flac", {BasicTag.ARTIST: ["A"], BasicTag.ALBUM: ["Foo"], BasicTag.TRACKNUMBER: ["03"], BasicTag.TITLE: ["three"]}),
            ],
        )
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
        ctx.select_albums = lambda _: [album]
        try:
            showed_issues = Checker(ctx, automatic=False, preview=False, fix=False, interactive=False, show_ignore_option=False).run_enabled()
            assert showed_issues == 0
        finally:
            ctx.db.dispose()

    def test_run_enabled_automatic_dependent_check_ok(self):
        album = Album(
            "foo" + os.sep,
            [Track("1-01 one.flac", {BasicTag.ARTIST: ["A"], BasicTag.ALBUM: ["Foo"], BasicTag.TRACKNUMBER: ["1-01"], BasicTag.TITLE: ["one"]})],
        )
        ctx = Context()
        ctx.config.library = create_library("checker_automatic", [album])
        ctx.db = connection.open(connection.MEMORY)
        try:
            ctx.select_albums = lambda _: selector.load_albums(ctx.db)
            scanner.scan(ctx)
            showed_issues = Checker(ctx, automatic=True, preview=False, fix=False, interactive=False, show_ignore_option=False).run_enabled()

            # there is only 1 issue "disc-in-tracknumber" and if "invalid-track-or-disc-number" check sees the FIXED album it will report no problem
            assert showed_issues == 1

            album = next(ctx.select_albums(True))
            assert album.tracks[0].tags[BasicTag.DISCNUMBER] == ("1",)
            assert album.tracks[0].tags[BasicTag.TRACKNUMBER] == ("01",)
        finally:
            ctx.db.dispose()

    def test_run_enabled_dependent_check_failures(self, mocker):
        album = Album(
            "foo" + os.sep,
            [  # disc-in-track-number fails -> invalid-track-or-disc-number does not run -> other checks do not run
                Track("1.flac", {BasicTag.ALBUM: ["Foo"], BasicTag.TRACKNUMBER: ["1-01"], BasicTag.TITLE: ["one"]}),
                Track("2.flac", {BasicTag.ALBUM: ["Foo"], BasicTag.TRACKNUMBER: ["1-02"], BasicTag.TITLE: ["two"]}),
                Track("3.flac", {BasicTag.ALBUM: ["Foo"], BasicTag.TRACKNUMBER: ["1-03"], BasicTag.TITLE: ["three"]}),
            ],
        )
        ctx = Context()
        ctx.select_albums = lambda _: [album]
        ctx.db = connection.open(connection.MEMORY)
        try:
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
