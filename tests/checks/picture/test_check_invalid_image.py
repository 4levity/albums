from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.picture.check_invalid_image import CheckInvalidImage
from albums.database.models import AlbumEntity, PictureFileEntity, TrackEntity, TrackPictureEntity
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import PictureType, TaggerFile


class TestCheckCheckInvalidImage:
    def test_invalid_image_ok(self):
        pic = TrackPictureEntity(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT)
        album = AlbumEntity(
            path="",
            tracks=[TrackEntity(filename="1.flac", pictures=[pic])],
            picture_files=[PictureFileEntity(filename="cover.jpg", picture_info=pic.picture_info)],
        )
        assert not CheckInvalidImage(Context()).check(album)

    def test_error_image_in_track(self, mocker):
        pic = TrackPictureEntity(
            picture_info=PictureInfo("image/png", 400, 400, 24, 1, b"", (("error", "test load failed"),)), picture_type=PictureType.COVER_FRONT
        )
        album = AlbumEntity(path="", tracks=[TrackEntity(filename="1.flac", pictures=[pic])])
        result = CheckInvalidImage(Context()).check(album)
        assert result is not None
        assert "image load errors: test load failed" in result.message

        assert result.fixer
        assert result.fixer.option_automatic_index is None
        assert len(result.fixer.options) == 1
        assert "Remove/delete all invalid images" in result.fixer.options[0]

        tagger = TaggerFile()
        mock_remove_picture = mocker.patch.object(tagger, "remove_picture")
        bad_pic = TrackPictureEntity(
            picture_info=PictureInfo("", 0, 0, 0, 0, b"", (("error", dict(pic.picture_info.load_issue)["error"]),)),
            picture_type=PictureType.COVER_FRONT,
        )
        mock_get_pictures = mocker.patch.object(tagger, "get_pictures", return_value=[(bad_pic.to_picture(), b"")])
        mock_supports = mocker.patch.object(AlbumTagger, "supports", return_value=True)
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger

        fix_result = result.fixer.fix(result.fixer.options[0])
        assert fix_result
        assert mock_supports.call_count == 1
        assert mock_get_pictures.call_count == 1
        assert mock_remove_picture.call_count == 1
        assert mock_remove_picture.call_args_list[0][0][0].type == PictureType.COVER_FRONT
        assert mock_remove_picture.call_args_list[0][0][0].picture_info.load_issue == (("error", "test load failed"),)

    def test_error_image_in_file(self, mocker):
        pic = TrackPictureEntity(
            picture_info=PictureInfo("image/png", 400, 400, 24, 1, b"", (("error", "test load failed"),)), picture_type=PictureType.COVER_FRONT
        )
        album = AlbumEntity(
            path="",
            tracks=[TrackEntity(filename="1.flac")],
            picture_files=[PictureFileEntity(filename="cover.jpg", picture_info=pic.picture_info)],
        )
        result = CheckInvalidImage(Context()).check(album)
        assert result is not None
        assert "image load errors: test load failed" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index is None
        assert len(result.fixer.options) == 1
        assert "Remove/delete all invalid images" in result.fixer.options[0]

        mock_unlink = mocker.patch("albums.checks.picture.check_invalid_image.unlink")
        fix_result = result.fixer.fix(result.fixer.options[0])
        assert fix_result
        assert mock_unlink.call_args_list == [call(Path(album.path) / "cover.jpg")]
