from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.check_duplicate_images import CheckDuplicateImages
from albums.types import Album, Picture, PictureType, Stream, Track


class TestCheckDuplicateImages:
    def test_duplicate_images_ok(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")],
                ),
                Track(
                    "2.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")],
                ),
            ],
        )
        assert not CheckDuplicateImages(Context()).check(album)

    def test_multiple_images_in_track(self):
        pictures = [
            Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"1111"),
            Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"2222"),
        ]
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), pictures)])
        result = CheckDuplicateImages(Context()).check(album)
        assert result is not None
        assert "there are 2 different images for COVER_BACK in one or more files" in result.message

    def test_duplicate_image_in_track(self):
        pictures = [
            Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b""),
            Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b""),
        ]
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), pictures)])
        result = CheckDuplicateImages(Context()).check(album)
        assert result is not None
        assert "duplicate embedded image data in one or more files: COVER_BACK" in result.message

    def test_front_cover_duplicate_files(self, mocker):
        pic = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")
        picture_files = {"folder.png": pic, "cover.png": pic}
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [pic])], [], [], picture_files)
        result = CheckDuplicateImages(Context()).check(album)
        assert result is not None
        assert result.message == "same image data in multiple files: cover.png, folder.png"
        assert result.fixer
        assert result.fixer.options == ["cover.png", "folder.png"]
        assert result.fixer.option_automatic_index == 0

        mock_unlink = mocker.patch("albums.checks.helpers.unlink")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_unlink.call_args_list == [call(Path(album.path) / "folder.png")]
