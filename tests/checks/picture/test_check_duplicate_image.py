from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.picture.check_duplicate_image import CheckDuplicateImage
from albums.picture.info import PictureInfo
from albums.tagger.types import Picture, PictureType, StreamInfo
from albums.types import Album, PictureFile, Track


class TestCheckDuplicateImage:
    def test_duplicate_image_ok(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [
                        Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, "", ()),
                        Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_BACK, "", ()),
                    ],
                ),
                Track(
                    "2.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [
                        Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, "", ()),
                        Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_BACK, "", ()),
                    ],
                ),
            ],
        )
        assert not CheckDuplicateImage(Context()).check(album)

    def test_multiple_images_in_track(self):
        pictures = [
            Picture(PictureInfo("image/png", 400, 400, 24, 1, b"1111"), PictureType.COVER_BACK, "", ()),
            Picture(PictureInfo("image/png", 400, 400, 24, 1, b"2222"), PictureType.COVER_BACK, "", ()),
        ]
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), pictures)])
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert "there are 2 different images for COVER_BACK in one or more files" in result.message

    def test_duplicate_image_in_track(self):
        pictures = [
            Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_BACK, "", ()),
            Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_BACK, "", ()),
        ]
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), pictures)])
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert "duplicate embedded image data in one or more files: COVER_BACK" in result.message

    def test_cover_duplicate_files(self, mocker):
        pic = Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, "", ())
        picture_files = {"folder.png": PictureFile(pic, 0, False), "cover.png": PictureFile(pic, 0, False)}
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [pic])], [], [], picture_files)
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert result.message == "same image data in multiple files: cover.png, folder.png"
        assert result.fixer
        assert result.fixer.options == ["cover.png", "folder.png"]
        assert result.fixer.option_automatic_index == 0

        mock_unlink = mocker.patch("albums.checks.helpers.unlink")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_unlink.call_args_list == [call(Path(album.path) / "folder.png")]
