from albums.app import Context
from albums.checks.picture.check_conflicting_embedded import CheckConflictingEmbedded
from albums.picture.info import PictureInfo
from albums.tagger.types import PictureType
from albums.types import Album, Track, TrackPicture


class TestCheckConflictingEmbedded:
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
                )
            ],
        )
        assert not CheckConflictingEmbedded(Context()).check(album)

    def test_multiple_images_in_track(self):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    pictures=[
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b"1111"), picture_type=PictureType.COVER_BACK),
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b"2222"), picture_type=PictureType.COVER_BACK),
                    ],
                )
            ],
        )
        result = CheckConflictingEmbedded(Context()).check(album)
        assert result is not None
        assert "there are 2 different images for COVER_BACK in 1.flac" in result.message
