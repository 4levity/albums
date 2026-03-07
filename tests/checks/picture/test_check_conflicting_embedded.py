from albums.app import Context
from albums.checks.picture.check_conflicting_embedded import CheckConflictingEmbedded
from albums.picture.info import PictureInfo
from albums.tagger.types import Picture, PictureType, StreamInfo
from albums.types import Album, Track


class TestCheckConflictingEmbedded:
    def test_duplicate_image_ok(self):
        pictures = [
            Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, ""),
            Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_BACK, ""),
        ]
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), pictures)])
        assert not CheckConflictingEmbedded(Context()).check(album)

    def test_multiple_images_in_track(self):
        pictures = [
            Picture(PictureInfo("image/png", 400, 400, 24, 1, b"1111"), PictureType.COVER_BACK, ""),
            Picture(PictureInfo("image/png", 400, 400, 24, 1, b"2222"), PictureType.COVER_BACK, ""),
        ]
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), pictures)])
        result = CheckConflictingEmbedded(Context()).check(album)
        assert result is not None
        assert "there are 2 different images for COVER_BACK in 1.flac" in result.message
