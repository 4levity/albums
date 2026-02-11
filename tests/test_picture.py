import xxhash

from albums.library.picture import get_picture_metadata
from albums.types import Picture, PictureType

from .fixtures.empty_files import IMAGE_PNG_400X400


class TestPicture:
    def test_picture_eq(self):
        pic1 = Picture(PictureType.COVER_FRONT, "image/png", 100, 100, 1024, b"abcd", {"format": "incorrect"}, 999)
        pic2 = Picture(PictureType.COVER_FRONT, "image/png", 100, 100, 1024, b"abcd")
        assert pic1 == pic2  # metadata mismatch details and file modification timestamp don't count

        assert pic1 != Picture(PictureType.COVER_FRONT, "image/png", 100, 100, 1024, b"ffff")
        assert pic1 != Picture(PictureType.COVER_BACK, "image/png", 100, 100, 1024, b"abcd")
        assert pic1 != Picture(PictureType.COVER_FRONT, "image/png", 100, 100, 0, b"abcd")

    def test_get_picture_metadata(self):
        pic = get_picture_metadata(bytes(IMAGE_PNG_400X400), PictureType.ARTIST)
        assert pic.file_size == len(IMAGE_PNG_400X400)
        assert pic.format == "image/png"
        assert pic.height == pic.width == 400
        assert pic.file_hash == xxhash.xxh32_digest(IMAGE_PNG_400X400)

    def test_get_picture_metadata_error(self):
        badfile = b"not an image file"
        pic = get_picture_metadata(bytes(badfile), PictureType.ARTIST)
        assert pic.file_size == len(badfile)
        assert pic.format == "Unknown"
        assert pic.height == pic.width == 0
        assert pic.file_hash == xxhash.xxh32_digest(badfile)
        assert "cannot identify image file" in str(pic.load_issue["error"])
