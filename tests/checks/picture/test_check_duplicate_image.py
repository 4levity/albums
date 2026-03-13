from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.picture.check_duplicate_image import CheckDuplicateImage
from albums.picture.info import PictureInfo
from albums.tagger.types import PictureType
from albums.types import Album, PictureFile, Track, TrackPicture


class TestCheckDuplicateImage:
    def test_duplicate_image_ok(self):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    pictures=[
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK),
                    ],
                ),
                Track(
                    filename="2.flac",
                    pictures=[
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK),
                    ],
                ),
            ],
        )
        assert not CheckDuplicateImage(Context()).check(album)

    def test_duplicate_image_in_track(self):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    pictures=[
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK),
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK),
                    ],
                )
            ],
        )
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert "duplicate embedded image data in one or more files: COVER_BACK" in result.message

    def test_cover_duplicate_files(self, mocker):
        pic = TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT)
        album = Album(
            path="",
            tracks=[Track(filename="1.flac", pictures=[pic])],
            picture_files=[
                PictureFile(filename="folder.png", picture_info=pic.picture_info),
                PictureFile(filename="cover.png", picture_info=pic.picture_info),
            ],
        )
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
