from albums.app import Context
from albums.checks.check_album_art import CheckAlbumArt
from albums.types import Album, Picture, PictureType, Stream, Track


class TestCheckAlbumArt:
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
            [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 15 * 1024 * 1024, b"")])],
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "embedded image COVER_FRONT is over the configured limit (15.0 MiB > 8.0 MiB)"
