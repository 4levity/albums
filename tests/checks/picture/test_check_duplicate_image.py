from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.picture.check_duplicate_image import CheckDuplicateImage
from albums.database.models import AlbumEntity, PictureFileEntity, TrackEntity, TrackPictureEntity
from albums.picture.info import PictureInfo
from albums.tagger.types import PictureType


class TestCheckDuplicateImage:
    def test_duplicate_image_ok(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac",
                    pictures=[
                        TrackPictureEntity(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
                        TrackPictureEntity(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK),
                    ],
                ),
                TrackEntity(
                    filename="2.flac",
                    pictures=[
                        TrackPictureEntity(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
                        TrackPictureEntity(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK),
                    ],
                ),
            ],
        )
        assert not CheckDuplicateImage(Context()).check(album)

    def test_duplicate_image_in_track(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac",
                    pictures=[
                        TrackPictureEntity(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK),
                        TrackPictureEntity(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK),
                    ],
                )
            ],
        )
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert "duplicate embedded image data in one or more files: COVER_BACK" in result.message

    def test_cover_duplicate_files(self, mocker):
        pic = TrackPictureEntity(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT)
        album = AlbumEntity(
            path="",
            tracks=[TrackEntity(filename="1.flac", pictures=[pic])],
            picture_files=[
                PictureFileEntity(filename="folder.png", picture_info=pic.picture_info),
                PictureFileEntity(filename="cover.png", picture_info=pic.picture_info),
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
