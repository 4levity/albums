from albums.app import Context
from albums.checks.picture.check_album_art import CheckAlbumArt
from albums.types import Album, Picture, PictureType, Stream, Track


class TestCheckAlbumArt:
    def test_album_art_ok(self):
        album = Album(
            "", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 1024, b"")])]
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is None

    def test_album_art_format(self):
        album = Album(
            "", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/gif", 400, 400, 1024, b"")])]
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "embedded image COVER_FRONT is not a recommended format (image/gif)"

    def test_album_art_file_too_large(self):
        album = Album(
            "",
            [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 15 * 1024 * 1024, b"")])],
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "embedded image COVER_FRONT is over the configured limit (15.0 MiB > 8.0 MiB)"
