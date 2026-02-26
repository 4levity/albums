from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.picture.check_invalid_image import CheckInvalidImage
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import AlbumPicture, PictureInfo, PictureType, StreamInfo, TaggerFile
from albums.types import Album, Picture, Track


class TestCheckCheckInvalidImage:
    def test_invalid_image_ok(self):
        pic = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [pic])], [], [], {"cover.jpg": pic})
        assert not CheckInvalidImage(Context()).check(album)

    def test_error_image_in_track(self, mocker):
        pic = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"", "", {"error": "test load failed"})
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [pic])])
        result = CheckInvalidImage(Context()).check(album)
        assert result is not None
        assert "image load errors: test load failed" in result.message

        assert result.fixer
        assert result.fixer.option_automatic_index is None
        assert len(result.fixer.options) == 1
        assert "Remove/delete all invalid images" in result.fixer.options[0]

        tagger = TaggerFile()
        mock_remove_picture = mocker.patch.object(tagger, "remove_picture")
        bad_pic = AlbumPicture(PictureInfo("", 0, 0, 0, 0, b""), PictureType.COVER_FRONT, "", (("error", pic.load_issue["error"]),))
        mock_get_pictures = mocker.patch.object(tagger, "get_pictures", return_value=[(bad_pic, b"")])
        mock_supports = mocker.patch.object(AlbumTagger, "supports", return_value=True)
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger

        fix_result = result.fixer.fix(result.fixer.options[0])
        assert fix_result
        assert mock_supports.call_count == 1
        assert mock_get_pictures.call_count == 1
        assert mock_remove_picture.call_count == 1
        assert mock_remove_picture.call_args_list[0][0][0].picture_type == PictureType.COVER_FRONT
        assert mock_remove_picture.call_args_list[0][0][0].load_issue == (("error", "test load failed"),)

    def test_error_image_in_file(self, mocker):
        pic = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"", "", {"error": "test load failed"})
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"))], [], [], {"cover.jpg": pic})
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
