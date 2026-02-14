from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.check_invalid_image import CheckInvalidImage
from albums.types import Album, Picture, PictureType, Stream, Track


class TestCheckCheckInvalidImage:
    def test_invalid_image_ok(self):
        pic = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [pic])], [], [], {"cover.jpg": pic})
        assert not CheckInvalidImage(Context()).check(album)

    def test_error_image_in_track(self, mocker):
        pic = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"", "", {"error": "test load failed"})
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [pic])])
        result = CheckInvalidImage(Context()).check(album)
        assert result is not None
        assert "image load errors: test load failed" in result.message

        assert result.fixer
        assert result.fixer.option_automatic_index is None
        assert len(result.fixer.options) == 1
        assert "Remove/delete all invalid images" in result.fixer.options[0]

        mock_remove_embedded_image = mocker.patch("albums.checks.check_invalid_image.remove_embedded_image", return_value=True)
        fix_result = result.fixer.fix(result.fixer.options[0])
        assert fix_result
        assert mock_remove_embedded_image.call_args_list == [call(Path(album.path) / album.tracks[0].filename, "FLAC", pic)]

    def test_error_image_in_file(self, mocker):
        pic = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"", "", {"error": "test load failed"})
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))], [], [], {"cover.jpg": pic})
        result = CheckInvalidImage(Context()).check(album)
        assert result is not None
        assert "image load errors: test load failed" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index is None
        assert len(result.fixer.options) == 1
        assert "Remove/delete all invalid images" in result.fixer.options[0]

        mock_unlink = mocker.patch("albums.checks.check_invalid_image.unlink")
        fix_result = result.fixer.fix(result.fixer.options[0])
        assert fix_result
        assert mock_unlink.call_args_list == [call(Path(album.path) / "cover.jpg")]
