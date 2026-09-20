import os
from unittest.mock import call

import pytest
from rich.console import Console
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.check_types import FixResult
from albums.checks.fields.check_duplicate_album import CheckDuplicateAlbum
from albums.database import MEMORY, db_open
from albums.entities import Album, Track
from albums.tagger import BasicField


class TestCheckDuplicateAlbum:
    def test_duplicate_ok(self):
        albums = [
            Album(path="one" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="two" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "Two", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            assert not CheckDuplicateAlbum(ctx).check(albums[0])
            assert not CheckDuplicateAlbum(ctx).check(albums[1])

    def test_duplicate_exact_keep_this(self, mocker, tmp_path):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.config.library = tmp_path
        (tmp_path / "One (2001)").mkdir()
        (tmp_path / "One!").mkdir()
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            assert not CheckDuplicateAlbum(ctx).check(albums[1])  # one duplicate set is one problem: first album is the one that fails the check
            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result
            assert 'possible duplicate of "One!' in result.message
            assert result.fixer
            assert result.fixer.options == [
                f">> KEEP left (THIS album) and DELETE right (other): One!{os.sep}",
                f">> DELETE left (THIS album) and KEEP right (other): One!{os.sep}",
            ]
            assert result.fixer.option_automatic_index is None

            mock_rmtree = mocker.patch("albums.checks.fields.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm", return_value=True)
            fix_result = result.fixer.fix(result.fixer.options[0])

            assert fix_result == FixResult.CHANGED_OTHER
            assert mock_confirm.call_count == 1
            assert mock_rmtree.call_args_list == [call(tmp_path / "One!")]

    def test_duplicate_exact_keep_other(self, mocker, tmp_path):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.config.library = tmp_path
        (tmp_path / "One (2001)").mkdir()
        (tmp_path / "One!").mkdir()
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            assert not CheckDuplicateAlbum(ctx).check(albums[1])
            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result
            assert 'possible duplicate of "One!' in result.message
            assert result.fixer
            assert result.fixer.options == [
                f">> KEEP left (THIS album) and DELETE right (other): One!{os.sep}",
                f">> DELETE left (THIS album) and KEEP right (other): One!{os.sep}",
            ]
            assert result.fixer.option_automatic_index is None

            mock_rmtree = mocker.patch("albums.checks.fields.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm", return_value=True)
            fix_result = result.fixer.fix(result.fixer.options[1])

            assert fix_result == FixResult.DELETED_ALBUM
            assert mock_confirm.call_count == 1
            assert mock_rmtree.call_args_list == [call(tmp_path / "One (2001)")]

    def test_duplicate_delete_refused_subfolder(self, mocker, tmp_path):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.config.library = tmp_path
        (tmp_path / "One!" / "Disc 2").mkdir(parents=True)
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result and result.fixer

            mock_rmtree = mocker.patch("albums.checks.fields.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm", return_value=True)
            fix_result = result.fixer.fix(result.fixer.options[0])

            assert fix_result == FixResult.NO_CHANGE
            assert mock_confirm.call_count == 0
            assert not mock_rmtree.called
            assert (tmp_path / "One!").is_dir()

    def test_duplicate_delete_refused_symlink(self, mocker, tmp_path):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.config.library = tmp_path
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "precious.flac").write_text("data")
        (tmp_path / "One!").mkdir()
        try:
            os.symlink(outside, tmp_path / "One!" / "Disc 2")
        except OSError:
            pytest.skip("symlinks not supported on this platform")
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result and result.fixer

            mock_rmtree = mocker.patch("albums.checks.fields.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm", return_value=True)
            fix_result = result.fixer.fix(result.fixer.options[0])

            assert fix_result == FixResult.NO_CHANGE
            assert mock_confirm.call_count == 0
            assert not mock_rmtree.called
            assert (outside / "precious.flac").exists()

    def test_duplicate_delete_refused_path_is_file(self, mocker, tmp_path):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.config.library = tmp_path
        (tmp_path / "One!").write_text("not a folder")
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result and result.fixer

            mock_rmtree = mocker.patch("albums.checks.fields.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm", return_value=True)
            fix_result = result.fixer.fix(result.fixer.options[0])

            assert fix_result == FixResult.NO_CHANGE
            assert mock_confirm.call_count == 0
            assert not mock_rmtree.called
            assert (tmp_path / "One!").is_file()

    def test_duplicate_delete_extra_files_confirmed(self, mocker, tmp_path):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.config.library = tmp_path
        (tmp_path / "One!").mkdir()
        (tmp_path / "One!" / "1.flac").write_text("track in the database")
        (tmp_path / "One!" / "notes.txt").write_text("file not in the database")
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result and result.fixer

            mock_rmtree = mocker.patch("albums.checks.fields.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm", side_effect=[True, True])
            fix_result = result.fixer.fix(result.fixer.options[0])

            assert fix_result == FixResult.CHANGED_OTHER
            assert mock_confirm.call_count == 2
            assert mock_rmtree.call_args_list == [call(tmp_path / "One!")]

    def test_duplicate_delete_extra_files_declined(self, mocker, tmp_path):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.config.library = tmp_path
        (tmp_path / "One!").mkdir()
        (tmp_path / "One!" / "1.flac").write_text("track in the database")
        (tmp_path / "One!" / "notes.txt").write_text("file not in the database")
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result and result.fixer

            mock_rmtree = mocker.patch("albums.checks.fields.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm", side_effect=[False])
            fix_result = result.fixer.fix(result.fixer.options[0])

            assert fix_result == FixResult.NO_CHANGE
            assert mock_confirm.call_count == 1
            assert not mock_rmtree.called
            assert (tmp_path / "One!" / "notes.txt").exists()

    def test_duplicate_delete_ignores_os_files(self, mocker, tmp_path):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.config.library = tmp_path
        (tmp_path / "One!").mkdir()
        (tmp_path / "One!" / "1.flac").write_text("track in the database")
        (tmp_path / "One!" / ".DS_Store").write_text("os file")
        (tmp_path / "One!" / "Thumbs.db").write_text("os file")
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result and result.fixer

            mock_rmtree = mocker.patch("albums.checks.fields.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm", return_value=True)
            fix_result = result.fixer.fix(result.fixer.options[0])

            assert fix_result == FixResult.CHANGED_OTHER
            assert mock_confirm.call_count == 1  # only the general delete confirmation
            assert mock_rmtree.call_args_list == [call(tmp_path / "One!")]

    def test_duplicate_delete_other_missing(self, mocker, tmp_path):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        console = Console(record=True, width=120)
        ctx = Context()
        ctx.console = console
        ctx.config.library = tmp_path  # no "One!" folder on disk
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result and result.fixer

            mock_rmtree = mocker.patch("albums.checks.fields.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm")
            fix_result = result.fixer.fix(result.fixer.options[0])

            assert fix_result == FixResult.CHANGED_OTHER
            assert mock_confirm.call_count == 0
            assert not mock_rmtree.called
            # collapse line wraps: on Windows the long tmp path can wrap the warning mid-phrase
            assert "does not exist" in " ".join(console.export_text().split())

    def test_duplicate_delete_this_missing(self, mocker, tmp_path):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        console = Console(record=True, width=120)
        ctx = Context()
        ctx.console = console
        ctx.config.library = tmp_path  # no "One (2001)" folder on disk
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result and result.fixer

            mock_rmtree = mocker.patch("albums.checks.fields.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.fields.check_duplicate_album.confirm")
            fix_result = result.fixer.fix(result.fixer.options[1])

            assert fix_result == FixResult.DELETED_ALBUM
            assert mock_confirm.call_count == 0
            assert not mock_rmtree.called
            # collapse line wraps: on Windows the long tmp path can wrap the warning mid-phrase
            assert "does not exist" in " ".join(console.export_text().split())

    def test_duplicate_multiple(self):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(
                path="One [Regular Edition]" + os.sep,
                tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})],
            ),
        ]
        ctx = Context()
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.add(albums[2])
            session.flush()

            assert not CheckDuplicateAlbum(ctx).check(albums[1])
            assert not CheckDuplicateAlbum(ctx).check(albums[2])
            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result
            assert f'multiple duplicates: "One!{os.sep}", "One [Regular Edition]' in result.message
            assert not result.fixer

    def test_duplicate_case_insensitive(self):
        albums = [
            Album(
                path="One At A Time" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "One At A Time", BasicField.ARTIST: "Foo"})]
            ),
            Album(
                path="One at a Time" + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "One at a Time", BasicField.ARTIST: "Foo"})]
            ),
        ]
        ctx = Context()
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            assert not CheckDuplicateAlbum(ctx).check(albums[1])
            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result
            assert 'possible duplicate of "One at a Time' in result.message
            assert "no automatic fix because paths differ only in case" in result.message
            assert not result.fixer

    def test_duplicate_compilation(self):
        albums = [
            Album(
                path="Lots (2000)" + os.sep,
                tracks=[
                    Track(filename="1.flac", fields={BasicField.ALBUM: "Lots", BasicField.ARTIST: "Foo", BasicField.ALBUMARTIST: "Various Artists"}),
                    Track(filename="2.flac", fields={BasicField.ALBUM: "Lots", BasicField.ARTIST: "Bar", BasicField.ALBUMARTIST: "Various Artists"}),
                ],
            ),
            Album(
                path="Lots" + os.sep,
                tracks=[
                    Track(filename="2.flac", fields={BasicField.ALBUM: "Lots", BasicField.ARTIST: "Bar", BasicField.ALBUMARTIST: "Various Artists"}),
                    Track(filename="1.flac", fields={BasicField.ALBUM: "Lots", BasicField.ARTIST: "Foo", BasicField.ALBUMARTIST: "Various Artists"}),
                ],
            ),
        ]
        ctx = Context()
        ctx.db = db_open(MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            assert not CheckDuplicateAlbum(ctx).check(albums[1])
            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result
            assert f'possible duplicate of "Lots{os.sep}' in result.message
            assert result.fixer
