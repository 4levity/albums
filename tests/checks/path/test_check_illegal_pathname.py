import os
from pathlib import Path
from unittest.mock import call

import pytest

from albums.app import Context
from albums.checks.check_types import FixResult
from albums.checks.path.check_illegal_pathname import CheckIllegalPathname
from albums.config import PathCompatibilityOption
from albums.entities import Album, PictureFile, Track
from albums.picture import PictureInfo

from ...helpers import apply_automatic_fix

# It's hard to deal with illegal filenames in Windows/wine (that's why they're illegal), so tests that actually create them on disk are only run on Linux.
linux_only = pytest.mark.skipif(os.name == "nt", reason="illegal file/folder names like 'a:b' cannot exist on Windows")


def ctx_in(tmp_path: Path, album_path: str) -> Context:
    """A context whose library is tmp_path, with the album folder present on disk (and nothing else)."""
    ctx = Context()
    ctx.config.library = tmp_path
    (tmp_path / album_path).mkdir(parents=True, exist_ok=True)
    return ctx


class TestCheckIllegalPathname:
    def test_pathname_ok(self):
        album = Album(
            path="Foo" + os.sep,
            tracks=[Track(filename="normal.flac")],
            picture_files=[PictureFile(filename="normal.jpg", picture_info=PictureInfo("image/png", 1, 1, 24, 1, b""))],
        )
        assert not CheckIllegalPathname(Context()).check(album)

    def test_pathname_ok_at_library_root(self):
        album = Album(path=".", tracks=[Track(filename="normal.flac")])
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

    def test_pathname_fix(self, mocker, tmp_path):
        album = Album(path="Foo" + os.sep, tracks=[Track(filename="CON.flac")])
        ctx = ctx_in(tmp_path, "Foo" + os.sep)
        result = CheckIllegalPathname(ctx).check(album)
        assert result is not None
        assert "'CON' is a reserved name" in result.message
        assert result.fixer is not None
        assert result.fixer.options == [">> Sanitize all filenames"]

        table = result.fixer.get_table()
        assert table is not None
        (headers, rows) = table
        assert headers == ["Filename", "New Filename"]
        assert list(rows) == [["CON.flac", "[yellow]CON_.flac[/yellow]"]]

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [call(tmp_path / "Foo" / "CON.flac", tmp_path / "Foo" / "CON_.flac")]
        assert album.path == "Foo" + os.sep

    def test_pathname_fix_collision(self, mocker, tmp_path):
        # "a/b.flac" and "a?b.flac" both sanitize to "ab.flac", so a number is appended to the second one
        album = Album(path="Foo" + os.sep, tracks=[Track(filename="a/b.flac"), Track(filename="a?b.flac")])
        ctx = ctx_in(tmp_path, "Foo" + os.sep)
        result = CheckIllegalPathname(ctx).check(album)
        assert result is not None
        assert "invalid characters" in result.message
        assert result.fixer is not None

        table = result.fixer.get_table()
        assert table is not None
        (headers, rows) = table
        assert list(rows) == [
            ["a/b.flac", "[yellow]ab.flac[/yellow]"],
            ["a?b.flac", "[yellow]ab 1.flac[/yellow]"],
        ]

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [
            call(tmp_path / "Foo" / "a/b.flac", tmp_path / "Foo" / "ab.flac"),
            call(tmp_path / "Foo" / "a?b.flac", tmp_path / "Foo" / "ab 1.flac"),
        ]

    def test_pathname_fix_collision_with_existing_file(self, mocker, tmp_path):
        # "a:b.flac" sanitizes to "ab.flac" which already exists, so a number is appended
        album = Album(path="Foo" + os.sep, tracks=[Track(filename="a:b.flac"), Track(filename="ab.flac")])
        ctx = ctx_in(tmp_path, "Foo" + os.sep)
        (tmp_path / "Foo" / "ab.flac").write_bytes(b"")
        result = CheckIllegalPathname(ctx).check(album)
        assert result is not None
        assert "invalid characters" in result.message
        assert result.fixer is not None

        table = result.fixer.get_table()
        assert table is not None
        (headers, rows) = table
        assert list(rows) == [
            ["a:b.flac", "[yellow]ab 1.flac[/yellow]"],
            ["ab.flac", "[bold italic]no change[/bold italic]"],
        ]

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [call(tmp_path / "Foo" / "a:b.flac", tmp_path / "Foo" / "ab 1.flac")]

    def test_pathname_picture_file_fix(self, mocker, tmp_path):
        album = Album(
            path="Foo" + os.sep,
            tracks=[Track(filename="normal.flac")],
            picture_files=[PictureFile(filename="CON.jpg", picture_info=PictureInfo("image/png", 1, 1, 24, 1, b""))],
        )
        ctx = ctx_in(tmp_path, "Foo" + os.sep)
        result = CheckIllegalPathname(ctx).check(album)
        assert result is not None
        assert "'CON' is a reserved name" in result.message
        assert result.fixer is not None
        assert result.fixer.options == [">> Sanitize all filenames"]

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [call(tmp_path / "Foo" / "CON.jpg", tmp_path / "Foo" / "CON_.jpg")]

    def test_pathname_fix_renames_tracks_and_picture_files(self, mocker, tmp_path):
        album = Album(
            path="Foo" + os.sep,
            tracks=[Track(filename="a/b.flac"), Track(filename="normal.flac")],
            picture_files=[PictureFile(filename="a:b.jpg", picture_info=PictureInfo("image/png", 1, 1, 24, 1, b""))],
        )
        ctx = ctx_in(tmp_path, "Foo" + os.sep)
        result = CheckIllegalPathname(ctx).check(album)
        assert result is not None

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [
            call(tmp_path / "Foo" / "a/b.flac", tmp_path / "Foo" / "ab.flac"),
            call(tmp_path / "Foo" / "a:b.jpg", tmp_path / "Foo" / "ab.jpg"),
        ]

    def test_pathname_fix_table_includes_picture_files(self, tmp_path):
        album = Album(
            path="Foo" + os.sep,
            tracks=[Track(filename="a/b.flac"), Track(filename="normal.flac")],
            picture_files=[PictureFile(filename="a:b.jpg", picture_info=PictureInfo("image/png", 1, 1, 24, 1, b""))],
        )
        ctx = ctx_in(tmp_path, "Foo" + os.sep)
        result = CheckIllegalPathname(ctx).check(album)
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

    @linux_only
    def test_pathname_illegal_album_folder(self, mocker, tmp_path):
        album = Album(path="a:b" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = ctx_in(tmp_path, "a:b" + os.sep)
        result = CheckIllegalPathname(ctx).check(album)
        assert result is not None
        assert result.message == 'illegal folder name: "a:b" (should be "ab")'
        assert result.fixer is not None
        assert result.fixer.options == [">> Sanitize the folder name"]

        table = result.fixer.get_table()
        assert table is not None
        (headers, rows) = table
        assert headers == ["Filename", "New Filename"]
        assert list(rows) == [["a:b" + os.sep, "[yellow]ab" + os.sep + "[/yellow]"]]

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [call(tmp_path / "a:b", tmp_path / "ab")]
        assert album.path == "ab" + os.sep

    @linux_only
    def test_pathname_illegal_album_folder_case_insensitive_collision(self, mocker, tmp_path):
        # the sanitized name collides case-insensitively with the sibling folder "AB", so a number is appended
        album = Album(path="a:b" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = ctx_in(tmp_path, "a:b" + os.sep)
        (tmp_path / "AB").mkdir()
        result = CheckIllegalPathname(ctx).check(album)
        assert result is not None
        assert result.fixer is not None

        table = result.fixer.get_table()
        assert table is not None
        (headers, rows) = table
        assert list(rows) == [["a:b" + os.sep, "[yellow]ab 1" + os.sep + "[/yellow]"]]

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [call(tmp_path / "a:b", tmp_path / "ab 1")]
        assert album.path == "ab 1" + os.sep

    @linux_only
    def test_pathname_illegal_album_folder_collision_appears_before_fix(self, mocker, tmp_path):
        # the sibling folder is created after the table is rendered, so the fix re-checks the disk and adjusts
        album = Album(path="a:b" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = ctx_in(tmp_path, "a:b" + os.sep)
        result = CheckIllegalPathname(ctx).check(album)
        assert result is not None
        table = result.fixer.get_table()
        assert table is not None
        (headers, rows) = table
        assert list(rows) == [["a:b" + os.sep, "[yellow]ab" + os.sep + "[/yellow]"]]

        (tmp_path / "ab").mkdir()

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [call(tmp_path / "a:b", tmp_path / "ab 1")]
        assert album.path == "ab 1" + os.sep

    def test_pathname_illegal_parent_folder_no_fix(self):
        # renaming a parent folder would move other albums, so no fix is offered
        album = Album(path="a:b" + os.sep + "Album" + os.sep, tracks=[Track(filename="1.flac")])
        result = CheckIllegalPathname(Context()).check(album)
        assert result is not None
        assert result.fixer is None
        assert result.message == 'illegal folder name in album path: "a:b" (no automatic fix: rename manually, then run a full scan)'

    def test_pathname_illegal_parent_folders_no_fix(self):
        album = Album(path="a:b" + os.sep + "c:d" + os.sep + "Album" + os.sep, tracks=[Track(filename="1.flac")])
        result = CheckIllegalPathname(Context()).check(album)
        assert result is not None
        assert result.fixer is None
        assert result.message == 'illegal folder names in album path: "a:b", "c:d" (no automatic fix: rename manually, then run a full scan)'

    @linux_only
    def test_pathname_illegal_files_and_album_folder(self, mocker, tmp_path):
        album = Album(path="a:b" + os.sep, tracks=[Track(filename="CON.flac")])
        ctx = ctx_in(tmp_path, "a:b" + os.sep)
        result = CheckIllegalPathname(ctx).check(album)
        assert result is not None
        assert "illegal filename:" in result.message
        assert 'illegal folder name: "a:b" (should be "ab")' in result.message
        assert result.fixer is not None
        assert result.fixer.options == [">> Sanitize all filenames and the folder name"]

        table = result.fixer.get_table()
        assert table is not None
        (headers, rows) = table
        assert list(rows) == [
            ["CON.flac", "[yellow]CON_.flac[/yellow]"],
            ["a:b" + os.sep, "[yellow]ab" + os.sep + "[/yellow]"],
        ]

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [
            call(tmp_path / "a:b" / "CON.flac", tmp_path / "a:b" / "CON_.flac"),
            call(tmp_path / "a:b", tmp_path / "ab"),
        ]
        assert album.path == "ab" + os.sep

    def test_pathname_fix_at_library_root(self, mocker, tmp_path):
        # the album is the library folder itself, so there is no album folder to rename
        album = Album(path=".", tracks=[Track(filename="CON.flac")])
        ctx = ctx_in(tmp_path, ".")
        result = CheckIllegalPathname(ctx).check(album)
        assert result is not None
        assert result.fixer is not None
        assert result.fixer.options == [">> Sanitize all filenames"]

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_rename.call_args_list == [call(tmp_path / "CON.flac", tmp_path / "CON_.flac")]
        assert album.path == "."

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
