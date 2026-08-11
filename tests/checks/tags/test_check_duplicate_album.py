import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context, Session
from albums.checks.tags.check_duplicate_album import CheckDuplicateAlbum
from albums.database import connection
from albums.entities import Album, Track
from albums.tagger.types import BasicField


class TestCheckDuplicateAlbum:
    def test_duplicate_ok(self):
        albums = [
            Album(path="one" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="two" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "Two", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            assert not CheckDuplicateAlbum(ctx).check(albums[0])
            assert not CheckDuplicateAlbum(ctx).check(albums[1])

    def test_duplicate_exact_keep_this(self, mocker):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
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

            mock_rmtree = mocker.patch("albums.checks.tags.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.tags.check_duplicate_album.confirm", return_value=True)
            fix_result = result.fixer.fix(result.fixer.options[0])

            assert fix_result
            assert mock_confirm.call_count == 1
            assert mock_rmtree.call_args_list == [call(Path(albums[1].path))]

    def test_duplicate_exact_keep_other(self, mocker):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
        ]
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
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

            mock_rmtree = mocker.patch("albums.checks.tags.check_duplicate_album.rmtree")
            mock_confirm = mocker.patch("albums.checks.tags.check_duplicate_album.confirm", return_value=True)
            fix_result = result.fixer.fix(result.fixer.options[1])

            assert fix_result
            assert mock_confirm.call_count == 1
            assert mock_rmtree.call_args_list == [call(Path(albums[0].path))]

    def test_duplicate_multiple(self):
        albums = [
            Album(path="One (2001)" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(path="One!" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]),
            Album(
                path="One [Regular Edition]" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "The One", BasicField.ARTIST: "Foo"})]
            ),
        ]
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
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
                path="One At A Time" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "One At A Time", BasicField.ARTIST: "Foo"})]
            ),
            Album(
                path="One at a Time" + os.sep, tracks=[Track(filename="1.flac", tag={BasicField.ALBUM: "One at a Time", BasicField.ARTIST: "Foo"})]
            ),
        ]
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
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
                    Track(filename="1.flac", tag={BasicField.ALBUM: "Lots", BasicField.ARTIST: "Foo", BasicField.ALBUMARTIST: "Various Artists"}),
                    Track(filename="2.flac", tag={BasicField.ALBUM: "Lots", BasicField.ARTIST: "Bar", BasicField.ALBUMARTIST: "Various Artists"}),
                ],
            ),
            Album(
                path="Lots" + os.sep,
                tracks=[
                    Track(filename="2.flac", tag={BasicField.ALBUM: "Lots", BasicField.ARTIST: "Bar", BasicField.ALBUMARTIST: "Various Artists"}),
                    Track(filename="1.flac", tag={BasicField.ALBUM: "Lots", BasicField.ARTIST: "Foo", BasicField.ALBUMARTIST: "Various Artists"}),
                ],
            ),
        ]
        ctx = Context()
        ctx.db = connection.open(connection.MEMORY)
        with Session(ctx.db) as session:
            session.add(albums[0])
            session.add(albums[1])
            session.flush()

            assert not CheckDuplicateAlbum(ctx).check(albums[1])
            result = CheckDuplicateAlbum(ctx).check(albums[0])
            assert result
            assert f'possible duplicate of "Lots{os.sep}' in result.message
            assert result.fixer
