import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.path.check_illegal_pathname import CheckIllegalPathname
from albums.config import PathCompatibilityOption
from albums.picture.info import PictureInfo
from albums.types import Album, PictureFile, Track


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
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_illegal_pathname.rename")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_rename.call_args_list == [call(Path(album.path) / "CON.flac", Path(album.path) / "CON_.flac")]

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
