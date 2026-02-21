import contextlib
import os

import pytest
from rich.text import Text

from albums.app import Context
from albums.checks.checker import run_enabled
from albums.database import connection
from albums.types import Album, Track


class TestChecker:
    def test_run_enabled_all_ok(self):
        album = Album(
            "foo" + os.sep,
            [
                Track("01 one.flac", {"artist": ["A"], "album": ["Foo"], "tracknumber": ["01"], "title": ["one"]}),
                Track("02 two.flac", {"artist": ["A"], "album": ["Foo"], "tracknumber": ["02"], "title": ["two"]}),
                Track("03 three.flac", {"artist": ["A"], "album": ["Foo"], "tracknumber": ["03"], "title": ["three"]}),
            ],
        )
        ctx = Context()
        ctx.select_albums = lambda _: [album]
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            ctx.db = db
            showed_issues = run_enabled(ctx, False, False, False, False)
            assert showed_issues == 0

    def test_run_enabled_dependent_check_failures(self, mocker):
        album = Album(
            "foo" + os.sep,
            [  # disc-in-track-number fails -> invalid-track-or-disc-number does not run -> other checks do not run
                Track("1.flac", {"album": ["Foo"], "tracknumber": ["1-01"], "title": ["one"]}),
                Track("2.flac", {"album": ["Foo"], "tracknumber": ["1-02"], "title": ["two"]}),
                Track("3.flac", {"album": ["Foo"], "tracknumber": ["1-03"], "title": ["three"]}),
            ],
        )
        ctx = Context()
        ctx.select_albums = lambda _: [album]
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            ctx.db = db
            print_spy = mocker.spy(ctx.console, "print")
            run_enabled(ctx, False, False, False, False)
            output = " ".join((Text.from_markup(call_args.args[0]).plain for call_args in print_spy.call_args_list))
            assert f'track numbers formatted as number-dash-number, probably discnumber and tracknumber : "foo{os.sep}"' in output
            assert f'dependency not met for check invalid-track-or-disc-number on "foo{os.sep}": disc-in-track-number must pass first' in output
            assert f'dependency not met for check disc-numbering on "foo{os.sep}": invalid-track-or-disc-number must pass first' in output

    def test_run_invalid_config(self, mocker):
        ctx = Context()
        ctx.config.checks["invalid-track-or-disc-number"] = {"enabled": False}
        print_spy = mocker.spy(ctx.console, "print")
        with pytest.raises(SystemExit):
            run_enabled(ctx, False, False, False, False)
        output = " ".join((Text.from_markup(call_args.args[0]).plain for call_args in print_spy.call_args_list))
        assert "Configuration error" in output
        assert "invalid-track-or-disc-number required by" in output
