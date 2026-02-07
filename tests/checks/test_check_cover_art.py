from albums.app import Context
from albums.checks.check_cover_art import CheckCoverArt
from albums.types import Album, Picture, PictureType, Stream, Track


class TestCheckCoverArt:
    def test_cover_art_ok(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0)],
                ),
                Track(
                    "2.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0)],
                ),
            ],
        )
        assert not CheckCoverArt(Context()).check(album)

    def test_cover_art_missing_ok(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))])
        assert not CheckCoverArt(Context()).check(album)

    def test_cover_art_missing_required(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))])
        ctx = Context()
        ctx.config["checks"] = {CheckCoverArt.name: {"cover_front_required": True}}
        result = CheckCoverArt(ctx).check(album)
        assert result is not None
        assert result.message == "album does not have a COVER_FRONT picture"

    def test_cover_art_multiple_front(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0), Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0)],
                ),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0)]),
            ],
        )
        result = CheckCoverArt(Context()).check(album)
        assert result is not None
        assert result.message == "multiple COVER_FRONT pictures in one track"

    def test_cover_art_multiple_unique(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0)]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 500, 500, 0)]),
            ],
        )
        result = CheckCoverArt(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT pictures are not all the same"

    def test_cover_art_pictures_but_no_front(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0)]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0)]),
            ],
        )
        result = CheckCoverArt(Context()).check(album)
        assert result is not None
        assert result.message == "track has pictures but none is COVER_FRONT picture"

    def test_cover_art_inconsistent(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0)]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")),
            ],
        )
        result = CheckCoverArt(Context()).check(album)
        assert result is not None
        assert result.message == "some tracks have COVER_FRONT and some do not"

    def test_cover_art_not_square(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 401, 400, 0)])])
        result = CheckCoverArt(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (401x400)"

    def test_cover_art_format(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/gif", 400, 400, 0)])])
        result = CheckCoverArt(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is not a recommended format (image/gif)"

    def test_cover_art_too_small(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 10, 10, 0)])])
        result = CheckCoverArt(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too small (10x10)"

    def test_cover_art_too_large(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 9001, 9001, 0)])])
        result = CheckCoverArt(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too large (9001x9001)"
