import os
from pathlib import Path
from unittest.mock import call

from PIL import Image

from albums.app import Context
from albums.checks.path.check_cover_filename import CheckCoverFilename
from albums.database.models import AlbumEntity, PictureFileEntity, TrackEntity
from albums.picture.info import PictureInfo

from ...fixtures.create_library import make_image_data


class TestCheckCoverFilename:
    def test_cover_filename_ok1(self):
        assert not CheckCoverFilename(Context()).check(
            AlbumEntity(path=
                "",
                tracks=[TrackEntity(filename="1.flac")],
                picture_files=[PictureFileEntity(filename="cover.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b""))],
            )
        )

    def test_cover_filename_ok2(self):
        assert not CheckCoverFilename(Context()).check(
            AlbumEntity(path=
                "",
                tracks=[TrackEntity(filename="1.flac")],
                picture_files=[PictureFileEntity(filename="cover.png", picture_info=PictureInfo("image/png", 1, 1, 1, 1, b""))],
            )
        )

    def test_cover_filename_ok3(self):
        assert not CheckCoverFilename(Context()).check(
            AlbumEntity(path=
                "",
                tracks=[TrackEntity(filename="1.flac")],
                picture_files=[PictureFileEntity(filename="other.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b""))],
            )
        )

    def test_cover_filename_multiple_with_target(self):
        album = AlbumEntity(path=
            "Foo" + os.sep,
            tracks=[TrackEntity(filename="1.flac")],
            picture_files=[
                PictureFileEntity(filename="cover.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b"")),  # check will pass because this file exists
                PictureFileEntity(filename="folder.png", picture_info=PictureInfo("image/png", 1, 1, 1, 1, b"")),
            ],
        )
        assert not CheckCoverFilename(Context()).check(album)

    def test_cover_filename_multiple(self):
        album = AlbumEntity(path=
            "Foo" + os.sep,
            tracks=[TrackEntity(filename="1.flac")],
            picture_files=[
                PictureFileEntity(filename="folder.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b"")),
                PictureFileEntity(filename="folder.png", picture_info=PictureInfo("image/png", 1, 1, 1, 1, b"")),
            ],
        )
        result = CheckCoverFilename(Context()).check(album)
        assert result
        assert result.message == "multiple cover image files, don't know which to rename: folder.jpg, folder.png"
        assert not result.fixer

    def test_cover_filename_rename(self, mocker):
        album = AlbumEntity(path=
            "Foo" + os.sep,
            tracks=[TrackEntity(filename="1.flac")],
            picture_files=[PictureFileEntity(filename="folder.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b""))],
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
        album = AlbumEntity(path=
            "Foo" + os.sep,
            tracks=[TrackEntity(filename="1.flac")],
            picture_files=[PictureFileEntity(filename="folder.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b""))],
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

        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_rename.call_args_list == [call(Path(album.path) / "folder.jpg", Path(album.path) / "cover.jpg")]
        assert album.picture_files[0].filename == "cover.jpg"

    def test_cover_filename_rename_case_insensitive(self, mocker):
        album = AlbumEntity(path=
            "Foo" + os.sep,
            tracks=[TrackEntity(filename="1.flac")],
            picture_files=[PictureFileEntity(filename="Cover.JPG", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b""))],
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
        album = AlbumEntity(path=
            "Foo" + os.sep,
            tracks=[TrackEntity(filename="1.flac")],
            picture_files=[PictureFileEntity(filename="cover.png", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b""))],
        )
        ctx = Context()
        ctx.config.checks["cover-filename"]["filename"] = "cover.jpg"
        result = CheckCoverFilename(ctx).check(album)
        assert result
        assert result.message == "cover image has the wrong filename and type (expected .jpg): cover.png"
        assert result.fixer
        assert result.fixer.options == [">> Convert cover.png to cover.jpg"]
        assert result.fixer.option_automatic_index == 0

        image_data = make_image_data(400, 400, "PNG")
        mock_save = mocker.patch.object(Image.Image, "save")
        mock_read_binary_file = mocker.patch("albums.checks.path.check_cover_filename.read_binary_file", return_value=image_data)
        mock_unlink = mocker.patch("albums.checks.path.check_cover_filename.unlink")

        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert fix_result
        assert mock_read_binary_file.call_args_list == [call(Path(album.path) / "cover.png")]
        assert mock_unlink.call_args_list == [call(Path(album.path) / "cover.png")]
        assert mock_save.call_args_list == [call(Path(album.path) / "cover.jpg", quality=CheckCoverFilename.default_config["jpeg_quality"])]
