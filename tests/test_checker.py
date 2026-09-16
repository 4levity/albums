import os

import pytest
from rich.text import Text
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.checker import Checker
from albums.database import MEMORY, db_open
from albums.entities import Album, Track
from albums.interactive.interact import OPTION_DO_NOTHING
from albums.library import run_scan
from albums.selector import load_album_entities
from albums.tagger import BasicField

from .fixtures.create_library import create_library


class TestChecker:
    def test_run_enabled_all_ok(self):
        album = Album(
            path="Foo" + os.sep,
            tracks=[
                Track(
                    filename="01 one.flac",
                    tag={BasicField.ARTIST: "A", BasicField.ALBUM: "Foo", BasicField.TRACKNUMBER: "01", BasicField.TITLE: "one"},
                ),
                Track(
                    filename="02 two.flac",
                    tag={BasicField.ARTIST: "A", BasicField.ALBUM: "Foo", BasicField.TRACKNUMBER: "02", BasicField.TITLE: "two"},
                ),
                Track(
                    filename="03 three.flac",
                    tag={BasicField.ARTIST: "A", BasicField.ALBUM: "Foo", BasicField.TRACKNUMBER: "03", BasicField.TITLE: "three"},
                ),
            ],
        )
        ctx = Context()
        ctx.db = db_open(MEMORY)
        ctx.select_album_entities = lambda session, order_by="path": load_album_entities(session)
        try:
            with Session(ctx.db) as session:
                session.add(album)
                session.commit()
                showed_issues = Checker(ctx, automatic=False, fix=False, interactive=False, show_ignore_option=False).run_enabled(session)
            assert showed_issues == 0
        finally:
            ctx.db.dispose()

    def test_run_enabled_automatic_dependent_check_ok(self):
        album = Album(
            path="Foo" + os.sep,
            tracks=[
                Track(
                    filename="1-01 one.flac",
                    tag={BasicField.ARTIST: "A", BasicField.ALBUM: "Foo", BasicField.TRACKNUMBER: "1-01", BasicField.TITLE: "one"},
                )
            ],
        )
        ctx = Context()
        ctx.config.library = create_library("checker_automatic", [album])
        ctx.db = db_open(MEMORY, True)
        try:
            with Session(ctx.db) as session:
                ctx.select_album_entities = lambda session, order_by="path": load_album_entities(session)
                run_scan(ctx, session)
                session.commit()

                showed_issues = Checker(ctx, automatic=True, fix=False, interactive=False, show_ignore_option=False).run_enabled(session)

            # there is only 1 issue "disc-in-tracknumber" and if "invalid-track-or-disc-number" check sees the FIXED album it will report no problem
            assert showed_issues == 1

            with Session(ctx.db) as session:
                album = next(ctx.select_album_entities(session))
                assert album.tracks[0].get(BasicField.TRACKNUMBER) == ("01",)
                assert album.tracks[0].get(BasicField.DISCNUMBER) == ("1",)
        finally:
            ctx.db.dispose()

    def test_run_enabled_dependent_check_failures(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[  # disc-in-track-number fails -> invalid-track-or-disc-number does not run -> other checks do not run
                Track(filename="1.flac", tag={BasicField.ALBUM: "Foo", BasicField.TRACKNUMBER: "1-01", BasicField.TITLE: "one"}),
                Track(filename="2.flac", tag={BasicField.ALBUM: "Foo", BasicField.TRACKNUMBER: "1-02", BasicField.TITLE: "two"}),
                Track(filename="3.flac", tag={BasicField.ALBUM: "Foo", BasicField.TRACKNUMBER: "1-03", BasicField.TITLE: "three"}),
            ],
        )
        ctx = Context()
        ctx.db = db_open(MEMORY)
        ctx.select_album_entities = lambda session, order_by="path": load_album_entities(session)
        ctx.config.library = create_library("dependent_check_failures", [album])
        try:
            with Session(ctx.db) as session:
                session.add(album)
                session.commit()

                print_spy = mocker.spy(ctx.console, "print")
                Checker(ctx, automatic=False, fix=False, interactive=False, show_ignore_option=False).run_enabled(session)

            output = " ".join((Text.from_markup(call_args.args[0]).plain for call_args in print_spy.call_args_list))
            assert f'track numbers formatted as number-dash-number, probably discnumber and tracknumber : "foo{os.sep}"' in output
            assert f'dependency not met for check invalid-track-or-disc-number on "foo{os.sep}": disc-in-track-number must pass first' in output
            assert f'dependency not met for check disc-numbering on "foo{os.sep}": invalid-track-or-disc-number must pass first' in output
        finally:
            ctx.db.dispose()

    def test_run_enabled_implicitly_ignored_checks(self):
        # an ignored check is never run, and every check that depends on it, directly or transitively,
        # is implicitly ignored: none of them should run or report a dependency problem
        album = Album(
            path="Foo" + os.sep,
            tracks=[
                Track(
                    filename="1-01 one.flac",
                    tag={BasicField.ARTIST: "A", BasicField.ALBUM: "Foo", BasicField.TRACKNUMBER: "1-01", BasicField.TITLE: "one"},
                )
            ],
        )
        ctx = Context()
        ctx.config.library = create_library("checker_implicit_ignore", [album])
        ctx.db = db_open(MEMORY, True)
        try:
            with Session(ctx.db) as session:
                ctx.select_album_entities = lambda session, order_by="path": load_album_entities(session)
                run_scan(ctx, session)
                session.commit()

                album_entity = next(ctx.select_album_entities(session))
                album_entity.ignore_checks.append("disc-in-track-number")
                session.commit()

                showed_issues = Checker(ctx, automatic=False, fix=False, interactive=False, show_ignore_option=False).run_enabled(session)

            assert showed_issues == 0
        finally:
            ctx.db.dispose()

    def test_run_enabled_implicit_ignore_of_checks_after_new_ignore(self, mocker):
        # when the user ignores a check because its dependency failed, the checks that depend on the newly
        # ignored check must be implicitly ignored without further prompting or dependency messages
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(
                    filename="1-01 one.flac",
                    tag={BasicField.ARTIST: "A", BasicField.ALBUM: "foo", BasicField.TRACKNUMBER: "1-01", BasicField.TITLE: "one"},
                )
            ],
        )
        ctx = Context()
        ctx.config.library = create_library("checker_implicit_ignore_prompt", [album])
        ctx.db = db_open(MEMORY, True)
        try:
            with Session(ctx.db) as session:
                ctx.select_album_entities = lambda session, order_by="path": load_album_entities(session)
                run_scan(ctx, session)
                session.commit()

                mock_choice = mocker.patch("albums.interactive.interact.choice", return_value=OPTION_DO_NOTHING)
                mock_confirm = mocker.patch("albums.interactive.interact.confirm", return_value=True)
                print_spy = mocker.spy(ctx.console, "print")
                showed_issues = Checker(ctx, automatic=False, fix=False, interactive=True, show_ignore_option=True).run_enabled(session)

            output = " ".join(
                (
                    Text.from_markup(call_args.args[0]).plain
                    for call_args in print_spy.call_args_list
                    if call_args.args and isinstance(call_args.args[0], str)
                )
            )
            assert showed_issues == 2  # disc-in-track-number issue + dependency not met for invalid-track-or-disc-number
            assert f'dependency not met for check invalid-track-or-disc-number on "foo{os.sep}": disc-in-track-number must pass first' in output
            assert 'Ignoring check "invalid-track-or-disc-number" will also implicitly ignore these checks for this album:' in output
            assert (
                output.index("- disc-numbering")
                < output.index("- track-numbering")
                < output.index("- zero-pad-numbers")
                < output.index("- track-filename")
            )
            # the checks that depend on the newly ignored check were implicitly ignored, not reported
            assert "dependency not met for check disc-numbering" not in output
            assert "dependency not met for check track-numbering" not in output
            assert "dependency not met for check zero-pad-numbers" not in output
            assert "dependency not met for check track-filename" not in output
            assert mock_choice.call_count == 1
            assert mock_confirm.call_count == 1

            with Session(ctx.db) as session:
                album_entity = next(ctx.select_album_entities(session))
                assert album_entity.ignore_checks == ["invalid-track-or-disc-number"]
        finally:
            ctx.db.dispose()

    def test_run_invalid_config(self, mocker):
        ctx = Context()
        checks = dict(ctx.config.checks)
        checks["invalid-track-or-disc-number"] = {"enabled": False}
        ctx.config.checks = checks
        print_spy = mocker.spy(ctx.console, "print")
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                with pytest.raises(SystemExit):
                    Checker(ctx, automatic=False, fix=False, interactive=False, show_ignore_option=False).run_enabled(session)
        finally:
            ctx.db.dispose()
        output = " ".join((Text.from_markup(call_args.args[0]).plain for call_args in print_spy.call_args_list))
        assert "Configuration error" in output
        assert "invalid-track-or-disc-number required by" in output

    def test_run_enabled_delete_other_album(self, mocker):
        albums = [
            Album(
                path="One!" + os.sep,
                tracks=[
                    Track(
                        filename="01 a.flac",
                        tag={BasicField.ARTIST: "A", BasicField.ALBUM: "One!", BasicField.TRACKNUMBER: "01", BasicField.TITLE: "a"},
                    )
                ],
            ),
            Album(
                path="One" + os.sep,
                tracks=[Track(filename="1.flac", tag={BasicField.ARTIST: "A", BasicField.ALBUM: "One!", BasicField.TRACKNUMBER: "01"})],
            ),
        ]
        ctx = Context()
        ctx.config.library = create_library("checker_delete_album", albums)
        ctx.db = db_open(MEMORY, True)
        try:
            with Session(ctx.db) as session:
                ctx.select_album_entities = lambda session, order_by="path": load_album_entities(session)
                run_scan(ctx, session)
                session.commit()
                mock_choice = mocker.patch(
                    "albums.interactive.interact.choice",
                    return_value=f">> KEEP left (THIS album) and DELETE right (other): One{os.sep}",
                )
                mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm", return_value=True)
                showed_issues = Checker(ctx, automatic=True, fix=True, interactive=False, show_ignore_option=False).run_enabled(session)

                assert mock_choice.call_count == 1
                assert mock_confirm.call_count == 1
                assert showed_issues == 1

                after = list(ctx.select_album_entities(session))
                assert len(after) == 1
                assert after[0].path == "One!" + os.sep
        finally:
            ctx.db.dispose()

    def test_run_enabled_delete_this_album(self, mocker):
        albums = [
            Album(
                path="One!" + os.sep,
                tracks=[
                    Track(
                        filename="01 a.flac",
                        tag={BasicField.ARTIST: "A", BasicField.ALBUM: "One", BasicField.TRACKNUMBER: "01", BasicField.TITLE: "a"},
                    )
                ],
            ),
            Album(
                path="One" + os.sep,
                tracks=[
                    Track(
                        filename="01 a.flac",
                        tag={BasicField.ARTIST: "A", BasicField.ALBUM: "One", BasicField.TRACKNUMBER: "01", BasicField.TITLE: "a"},
                    )
                ],
            ),
        ]
        ctx = Context()
        ctx.config.library = create_library("checker_delete_album", albums)
        ctx.db = db_open(MEMORY, True)
        try:
            with Session(ctx.db) as session:
                ctx.select_album_entities = lambda s: load_album_entities(s)
                run_scan(ctx, session)
                session.commit()
                mock_choice = mocker.patch(
                    "albums.interactive.interact.choice",
                    return_value=f">> DELETE left (THIS album) and KEEP right (other): One{os.sep}",
                )
                mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm", return_value=True)
                showed_issues = Checker(ctx, automatic=True, fix=True, interactive=False, show_ignore_option=False).run_enabled(session)

                assert mock_choice.call_count == 1
                assert mock_confirm.call_count == 1
                assert showed_issues == 1

                after = list(ctx.select_album_entities(session))
                assert len(after) == 1
                assert after[0].path == "One" + os.sep
        finally:
            ctx.db.dispose()
