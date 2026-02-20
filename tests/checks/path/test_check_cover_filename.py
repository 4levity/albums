import os
from pathlib import Path
from unittest.mock import call

from PIL import Image

from albums.app import Context
from albums.checks.path.check_cover_filename import CheckCoverFilename
from albums.types import Album, Picture, PictureType, Track


class TestCheckCoverFilename:
    def test_cover_filename_ok(self):
        o = CheckCoverFilename(Context())
        assert not o.check(Album("", [Track("1.flac")], [], [], {"cover.jpg": Picture(PictureType.COVER_FRONT, "image/jpeg", 1, 1, 1, b"")}))
        assert not o.check(Album("", [Track("1.flac")], [], [], {"cover.png": Picture(PictureType.COVER_FRONT, "image/png", 1, 1, 1, b"")}))

    def test_cover_filename_multiple_with_target(self):
        album = Album(
            "Foo" + os.sep,
            [Track("1.flac")],
            [],
            [],
            {
                "cover.jpg": Picture(PictureType.COVER_FRONT, "image/jpeg", 1, 1, 1, b""),  # check will pass because this file exists
                "folder.png": Picture(PictureType.COVER_FRONT, "image/png", 1, 1, 1, b""),
            },
        )
        assert not CheckCoverFilename(Context()).check(album)

    def test_cover_filename_multiple(self):
        album = Album(
            "Foo" + os.sep,
            [Track("1.flac")],
            [],
            [],
            {
                "folder.jpg": Picture(PictureType.COVER_FRONT, "image/jpeg", 1, 1, 1, b""),
                "folder.png": Picture(PictureType.COVER_FRONT, "image/png", 1, 1, 1, b""),
            },
        )
        result = CheckCoverFilename(Context()).check(album)
        assert result
        assert result.message == "multiple cover image files, don't know which to rename: folder.jpg, folder.png"
        assert not result.fixer

    def test_cover_filename_rename(self, mocker):
        album = Album(
            "Foo" + os.sep,
            [Track("1.flac")],
            [],
            [],
            {"folder.jpg": Picture(PictureType.COVER_FRONT, "image/jpeg", 1, 1, 1, b"")},
        )
        result = CheckCoverFilename(Context()).check(album)
        assert result
        assert result.message == "cover image has the wrong filename: folder.jpg"
        assert result.fixer
        assert result.fixer.options == [">> Rename folder.jpg to cover.jpg"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_cover_filename.rename")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_rename.call_args_list == [call(Path(album.path) / "folder.jpg", Path(album.path) / "cover.jpg")]

    def test_cover_filename_rename_cover_source(self, mocker):
        album = Album(
            "Foo" + os.sep,
            [Track("1.flac")],
            [],
            [],
            {"folder.jpg": Picture(PictureType.COVER_FRONT, "image/jpeg", 1, 1, 1, b"", "", None, 999, 0, True)},
            1,
        )
        ctx = Context()
        ctx.db = True
        result = CheckCoverFilename(ctx).check(album)
        assert result
        assert result.message == "cover image has the wrong filename: folder.jpg"
        assert result.fixer
        assert result.fixer.options == [">> Rename folder.jpg to cover.jpg"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_cover_filename.rename")
        mock_update_picture_files = mocker.patch("albums.checks.path.check_cover_filename.update_picture_files")

        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_rename.call_args_list == [call(Path(album.path) / "folder.jpg", Path(album.path) / "cover.jpg")]
        assert mock_update_picture_files.call_count == 1
        assert mock_update_picture_files.call_args.args == (True, 1, {"cover.jpg": Picture(PictureType.COVER_FRONT, "image/jpeg", 1, 1, 1, b"")})

    def test_cover_filename_rename_case_insensitive(self, mocker):
        album = Album(
            "Foo" + os.sep,
            [Track("1.flac")],
            [],
            [],
            {"Cover.JPG": Picture(PictureType.COVER_FRONT, "image/jpeg", 1, 1, 1, b"")},
        )
        result = CheckCoverFilename(Context()).check(album)
        assert result
        assert result.message == "cover image has the wrong filename: Cover.JPG"
        assert result.fixer
        assert result.fixer.options == [">> Rename Cover.JPG to cover.JPG"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_cover_filename.rename")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_rename.call_args_list == [
            call(Path(album.path) / "Cover.JPG", Path(album.path) / "Cover.0"),
            call(Path(album.path) / "Cover.0", Path(album.path) / "cover.JPG"),
        ]

    def test_cover_filename_convert(self, mocker):
        album = Album(
            "Foo" + os.sep,
            [Track("1.flac")],
            [],
            [],
            {"cover.png": Picture(PictureType.COVER_FRONT, "image/png", 1, 1, 1, b"")},
        )
        ctx = Context()
        ctx.config.checks["cover-filename"]["filename"] = "cover.jpg"
        result = CheckCoverFilename(ctx).check(album)
        assert result
        assert result.message == "cover image has the wrong filename and type (expected .jpg): cover.png"
        assert result.fixer
        assert result.fixer.options == [">> Convert cover.png to cover.jpg"]
        assert result.fixer.option_automatic_index == 0

        read_image_value = (Image.new("RGB", (400, 400), color="blue"), b"file contents")
        mock_save = mocker.patch.object(Image.Image, "save")
        mock_read_image = mocker.patch("albums.checks.path.check_cover_filename.read_image", return_value=read_image_value)
        mock_unlink = mocker.patch("albums.checks.path.check_cover_filename.unlink")

        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert fix_result
        assert mock_read_image.call_args_list == [call(Path(album.path) / "cover.png", False, 0)]
        assert mock_unlink.call_args_list == [call(Path(album.path) / "cover.png")]
        assert mock_save.call_args_list == [call(Path(album.path) / "cover.jpg", quality=CheckCoverFilename.default_config["jpeg_quality"])]
