from albums.app import Context
from albums.checks.check_album_art import CheckAlbumArt
from albums.types import Album, Picture, PictureType, Stream, Track


class TestCheckAlbumArt:
    def test_album_art_ok(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")],
                ),
                Track(
                    "2.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")],
                ),
            ],
        )
        assert not CheckAlbumArt(Context()).check(album)

    def test_album_art_missing_ok(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))])
        assert not CheckAlbumArt(Context()).check(album)

    def test_album_art_missing_required(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))])
        ctx = Context()
        ctx.config["checks"] = {CheckAlbumArt.name: {"cover_front_required": True}}
        result = CheckAlbumArt(ctx).check(album)
        assert result is not None
        assert result.message == "album does not have a COVER_FRONT picture"

    def test_album_art_multiple_front(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [
                        Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""),
                        Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""),
                    ],
                ),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
            ],
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "multiple COVER_FRONT pictures in one track"

    def test_album_art_multiple_unique(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 500, 500, 0, b"")]),
            ],
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT pictures are not all the same"

    def test_album_art_pictures_but_no_front(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")]),
            ],
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "album has pictures but none is COVER_FRONT picture"

    def test_album_art_inconsistent(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")),
            ],
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "some tracks have COVER_FRONT and some do not"

    def test_album_art_square_enough(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 401, 400, 0, b"")])])
        result = CheckAlbumArt(Context()).check(album)
        assert result is None

    def test_album_art_not_square_enough(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 420, 400, 0, b"")])])
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (420x400)"

    def test_album_art_format(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/gif", 400, 400, 0, b"")])])
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "embedded image COVER_FRONT is not a recommended format (image/gif)"

    def test_album_art_dimensions_too_small(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 10, 10, 0, b"")])])
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too small (10x10)"

    def test_album_art_dimensions_too_large(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 9001, 9001, 0, b"")])])
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too large (9001x9001)"

    def test_album_art_file_too_large(self):
        album = Album(
            "",
            [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 64 * 1024 * 1024, b"")])],
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "embedded image COVER_FRONT is over the configured limit (64.0 MiB > 8.0 MiB)"

    def test_album_art_metadata_mismatch(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"", {"format": "image/jpeg"})],
                )
            ],
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "embedded image metadata mismatch, actual image/png 400x400 but container says image/jpeg 400x400"
