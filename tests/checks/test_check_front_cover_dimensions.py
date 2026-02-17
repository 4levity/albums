from albums.app import Context
from albums.checks.check_front_cover_dimensions import CheckFrontCoverDimensions
from albums.types import Album, Picture, PictureType, Stream, Track


class TestCheckFrontCoverDimensions:
    def test_cover_square_enough(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 401, 400, 0, b"")])])
        result = CheckFrontCoverDimensions(Context()).check(album)
        assert result is None

    def test_cover_not_square_enough(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 420, 400, 0, b"")])])
        result = CheckFrontCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (420x400)"

    def test_cover_dimensions_too_small(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 10, 10, 0, b"")])])
        result = CheckFrontCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too small (10x10)"

    def test_cover_dimensions_too_large(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 9001, 9001, 0, b"")])])
        result = CheckFrontCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too large (9001x9001)"
