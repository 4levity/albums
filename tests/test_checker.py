import contextlib

import pytest
from rich.text import Text

from albums.app import Context
from albums.checks.checker import run_enabled
from albums.database import connection
from albums.types import Album, Track


class TestChecker:
    def test_run_enabled_all_ok(self):
        album = Album(
            "Foo/",
            [
                Track("1.flac", {"artist": ["A"], "album": ["Foo"], "tracknumber": ["01"], "title": ["one"]}),
                Track("2.flac", {"artist": ["A"], "album": ["Foo"], "tracknumber": ["02"], "title": ["two"]}),
                Track("3.flac", {"artist": ["A"], "album": ["Foo"], "tracknumber": ["03"], "title": ["three"]}),
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
            "Foo/",
            [  # disc_in_track_number fails -> invalid_track_or_disc_number does not run -> other checks do not run
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
            assert 'track numbers formatted as number-dash-number, probably discnumber and tracknumber : "Foo/"' in output
            assert 'dependency not met for check invalid_track_or_disc_number on "Foo/": disc_in_track_number must pass first' in output
            assert 'dependency not met for check disc_numbering on "Foo/": invalid_track_or_disc_number must pass first' in output

    def test_run_invalid_config(self, mocker):
        ctx = Context()
        ctx.config["checks"] = {"invalid_track_or_disc_number": {"enabled": False}}
        print_spy = mocker.spy(ctx.console, "print")
        with pytest.raises(SystemExit):
            run_enabled(ctx, False, False, False, False)
        output = " ".join((Text.from_markup(call_args.args[0]).plain for call_args in print_spy.call_args_list))
        assert "Configuration error" in output
        assert "invalid_track_or_disc_number required by" in output
