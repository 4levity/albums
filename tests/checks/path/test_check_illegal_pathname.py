import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.check_types import FixResult
from albums.checks.path.check_illegal_pathname import CheckIllegalPathname
from albums.config import PathCompatibilityOption
from albums.entities import Album, PictureFile, Track
from albums.picture import PictureInfo

from ...helpers import apply_automatic_fix


class TestCheckIllegalPathname:
    def test_pathname_ok(self):
        album = Album(
            path="Foo" + os.sep,
            tracks=[Track(filename="normal.flac")],
            picture_files=[PictureFile(filename="normal.jpg", picture_info=PictureInfo("image/png", 1, 1, 24, 1, b""))],
        )
        assert not CheckIllegalPathname(Context()).check(album)

    def test_pathname_reserved_name_universal(self):
        result = CheckIllegalPathname(Context()).check(Album(path="Foo" + os.sep, tracks=[Track(filename=":.flac")]))
        assert result is not None
        assert "':' is a reserved name" in result.message
        assert "platform=universal" in result.message

    def test_pathname_reserved_character_universal(self):
        result = CheckIllegalPathname(Context()).check(Album(path="Foo" + os.sep, tracks=[Track(filename="a/b.flac")]))
        assert result is not None
        assert "invalid characters found: invalids=('/')" in result.message
        assert "platform=universal" in result.message

    def test_pathname_reserved_name_Windows(self):
        result = CheckIllegalPathname(Context()).check(Album(path="Foo" + os.sep, tracks=[Track(filename="CON.flac")]))
        assert result is not None
        assert "'CON' is a reserved name" in result.message
        assert "platform=universal" in result.message

    def test_pathname_fix(self, mocker):
        album = Album(path="Foo" + os.sep, tracks=[Track(filename="CON.flac")])
        result = CheckIllegalPathname(Context()).check(album)
        assert result is not None
        assert "'CON' is a reserved name" in result.message
        assert result.fixer is not None
        assert result.fixer.options == [">> Sanitize all filenames"]

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [call(Path(album.path) / "CON.flac", Path(album.path) / "CON_.flac")]

    def test_pathname_fix_collision(self):
        # "a/b.flac" and "a?b.flac" both sanitize to "ab.flac", so no automatic fix is offered
        album = Album(path="Foo" + os.sep, tracks=[Track(filename="a/b.flac"), Track(filename="a?b.flac")])
        result = CheckIllegalPathname(Context()).check(album)
        assert result is not None
        assert "invalid characters" in result.message
        assert "automatic fix not possible due to filename conflict" in result.message
        assert result.fixer is None

    def test_pathname_fix_collision_with_existing_file(self):
        # "a:b.flac" sanitizes to "ab.flac" which already exists, so no automatic fix is offered
        album = Album(path="Foo" + os.sep, tracks=[Track(filename="a:b.flac"), Track(filename="ab.flac")])
        result = CheckIllegalPathname(Context()).check(album)
        assert result is not None
        assert "invalid characters" in result.message
        assert "automatic fix not possible due to filename conflict" in result.message
        assert result.fixer is None

    def test_pathname_picture_file_fix(self, mocker):
        album = Album(
            path="Foo" + os.sep,
            tracks=[Track(filename="normal.flac")],
            picture_files=[PictureFile(filename="CON.jpg", picture_info=PictureInfo("image/png", 1, 1, 24, 1, b""))],
        )
        result = CheckIllegalPathname(Context()).check(album)
        assert result is not None
        assert "'CON' is a reserved name" in result.message
        assert result.fixer is not None
        assert result.fixer.options == [">> Sanitize all filenames"]

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [call(Path(album.path) / "CON.jpg", Path(album.path) / "CON_.jpg")]

    def test_pathname_fix_renames_tracks_and_picture_files(self, mocker):
        album = Album(
            path="Foo" + os.sep,
            tracks=[Track(filename="a/b.flac"), Track(filename="normal.flac")],
            picture_files=[PictureFile(filename="a:b.jpg", picture_info=PictureInfo("image/png", 1, 1, 24, 1, b""))],
        )
        result = CheckIllegalPathname(Context()).check(album)
        assert result is not None

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [
            call(Path(album.path) / "a/b.flac", Path(album.path) / "ab.flac"),
            call(Path(album.path) / "a:b.jpg", Path(album.path) / "ab.jpg"),
        ]

    def test_pathname_fix_table_includes_picture_files(self):
        album = Album(
            path="Foo" + os.sep,
            tracks=[Track(filename="a/b.flac"), Track(filename="normal.flac")],
            picture_files=[PictureFile(filename="a:b.jpg", picture_info=PictureInfo("image/png", 1, 1, 24, 1, b""))],
        )
        result = CheckIllegalPathname(Context()).check(album)
        assert result is not None
        assert result.fixer is not None
        table = result.fixer.get_table()
        assert table is not None
        (headers, rows) = table
        assert headers == ["Filename", "New Filename"]
        assert list(rows) == [
            ["a/b.flac", "[yellow]ab.flac[/yellow]"],
            ["normal.flac", "[bold italic]no change[/bold italic]"],
            ["a:b.jpg", "[yellow]ab.jpg[/yellow]"],
        ]

    def test_pathname_reserved_character_Windows(self):
        result = CheckIllegalPathname(Context()).check(Album(path="Foo" + os.sep, tracks=[Track(filename="a:b.flac")]))
        assert result is not None
        assert "invalid characters found: invalids=(':')" in result.message
        # not sure why pathvalidate reports this as "Windows" when platform="universal", while CON.flac validation reports as "universal"?
        assert "platform=Windows" in result.message

    def test_pathname_ok_Linux(self):
        ctx = Context()
        ctx.config.path_compatibility = PathCompatibilityOption.LINUX
        assert not CheckIllegalPathname(ctx).check(Album(path="Foo" + os.sep, tracks=[Track(filename=":.flac")]))

    def test_pathname_reserved_character_Linux(self):
        ctx = Context()
        ctx.config.path_compatibility = PathCompatibilityOption.LINUX
        result = CheckIllegalPathname(ctx).check(Album(path="Foo" + os.sep, tracks=[Track(filename="a/b.flac")]))
        assert result is not None
        assert "invalid characters found: invalids=('/')" in result.message
        assert "platform=universal" in result.message
