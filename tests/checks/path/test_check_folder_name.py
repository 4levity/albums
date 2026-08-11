import os
from unittest.mock import call

from sqlalchemy import select
from sqlalchemy.orm import Session

from albums.app import Context, Path
from albums.checks.path.check_folder_name import CheckFolderName
from albums.database import connection
from albums.entities import Album, Track
from albums.library import scanner
from albums.tagger.types import BasicTag

from ...fixtures.create_library import create_library


class TestCheckFolderName:
    def test_folder_name_ok(self):
        album = Album(path="Foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicTag.ALBUM: "Foo"})])
        assert not CheckFolderName(Context()).check(album)

    def test_folder_name_ok_artist(self):
        album = Album(path="Bar - Foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicTag.ALBUM: "Foo", BasicTag.ARTIST: "Bar"})])
        ctx = Context()
        ctx.config.checks[CheckFolderName.name]["format"] = "$artist - $album"
        assert not CheckFolderName(ctx).check(album)

    def test_folder_name_ok_albumartist(self):
        album = Album(
            path="Various Artists - Foo" + os.sep,
            tracks=[
                Track(filename="1.flac", tag={BasicTag.ALBUM: "Foo", BasicTag.ARTIST: "Bar", BasicTag.ALBUMARTIST: "Various Artists"}),
                Track(filename="1.flac", tag={BasicTag.ALBUM: "Foo", BasicTag.ARTIST: "Baz", BasicTag.ALBUMARTIST: "Various Artists"}),
            ],
        )
        ctx = Context()
        ctx.config.checks[CheckFolderName.name]["format"] = "$artist - $album"
        assert not CheckFolderName(ctx).check(album)

    def test_folder_name_ok_no_info(self):
        album = Album(path="Foo" + os.sep, tracks=[Track(filename="1.flac")])
        assert not CheckFolderName(Context()).check(album)

    def test_folder_name_library_root(self):
        album = Album(path=".", tracks=[Track(filename="1.flac", tag={BasicTag.ALBUM: "Foo"})])
        assert not CheckFolderName(Context()).check(album)

    def test_folder_name_fix(self, mocker):
        album = Album(path="Foo (2026)" + os.sep, tracks=[Track(filename="1.flac", tag={BasicTag.ALBUM: "Foo"})])
        result = CheckFolderName(Context()).check(album)
        assert result
        assert "folder name does not match pattern" in result.message
        assert result.fixer
        assert result.fixer.options == ['>> Rename folder to "Foo"']
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_folder_name.rename")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_rename.call_args_list == [call(Path("Foo (2026)"), Path("Foo"))]
        assert album.path == "Foo" + os.sep

    def test_folder_name_fix_case_sensitive(self, mocker):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicTag.ALBUM: "Foo"})])
        result = CheckFolderName(Context()).check(album)
        assert result
        assert "folder name does not match pattern" in result.message
        assert result.fixer
        assert result.fixer.options == ['>> Rename folder to "Foo"']
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_folder_name.rename")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_rename.call_args_list == [call(Path("foo"), Path("foo.0")), call(Path("foo.0"), Path("Foo"))]
        assert album.path == "Foo" + os.sep

    def test_folder_name_preserve_db_entry(self, mocker):
        ctx = Context()
        ctx.config.library = create_library(
            "folder_name", [Album(path="Foo (2026)" + os.sep, tracks=[Track(filename="1.flac", tag={BasicTag.ALBUM: "Foo"})])]
        )
        ctx.db = connection.open(connection.MEMORY)
        try:
            with Session(ctx.db) as session:
                scanner.scan(ctx, session)
                (album,) = session.execute(select(Album)).tuples().one()
                album.ignore_checks.append("cover-unique")
                session.commit()

                result = CheckFolderName(ctx).check(album)
                assert result.fixer
                assert result.fixer.option_automatic_index == 0
                assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
                session.flush()

                (album,) = session.execute(select(Album)).tuples().one()
                assert album.path == "Foo" + os.sep
                assert "cover-unique" in album.ignore_checks

                assert not (ctx.config.library / "Foo (2026)").exists()
                assert (ctx.config.library / "Foo").exists()

                (_, any_changes) = scanner.scan(ctx, session)
                (album,) = session.execute(select(Album)).tuples().one()
                assert "cover-unique" in album.ignore_checks
                assert not any_changes

        finally:
            ctx.db.dispose()

    def test_folder_name_conflict(self, mocker):
        ctx = Context()
        album = Album(path="Foo (2026)" + os.sep, tracks=[Track(filename="1.flac", tag={BasicTag.ALBUM: "Foo"})])
        conflicting_album = Album(path="Foo" + os.sep, tracks=[Track(filename="1.flac", tag={BasicTag.ALBUM: "Foo"})])
        ctx.config.library = create_library("folder_name_conflict", [album, conflicting_album])

        result = CheckFolderName(ctx).check(album)
        assert result
        assert result.message == "folder name does not match pattern, but new path already exists: Foo"
        assert not result.fixer
