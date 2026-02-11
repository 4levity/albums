from albums.app import Context
from albums.checks.check_invalid_image import CheckInvalidImage
from albums.types import Album, Picture, PictureType, Stream, Track


class TestCheckCheckInvalidImage:
    def test_invalid_image_ok(self):
        pic = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [pic])], [], [], {"cover.jpg": pic})
        assert not CheckInvalidImage(Context()).check(album)

    def test_error_image_in_track(self):
        pic = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"", {"error": "couldn't load image"})
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [pic])])
        result = CheckInvalidImage(Context()).check(album)
        assert result is not None
        assert "invalid images (couldn't load image): 1.flac#0" in result.message

    def test_error_image_in_file(self):
        pic = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"", {"error": "couldn't load image"})
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))], [], [], {"cover.jpg": pic})
        result = CheckInvalidImage(Context()).check(album)
        assert result is not None
        assert "invalid images (couldn't load image): cover.jpg" in result.message
