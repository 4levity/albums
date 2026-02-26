import xxhash

from albums.tagger.picture import PictureScanner
from albums.tagger.types import PictureInfo, PictureType
from albums.types import Picture

from ..fixtures.create_library import make_image_data


class TestPicture:
    def test_picture_eq(self):
        pic1 = Picture(PictureType.COVER_FRONT, "image/png", 100, 100, 1024, b"abcd", load_issue={"format": "incorrect"}, modify_timestamp=999)
        pic2 = Picture(PictureType.COVER_FRONT, "image/png", 100, 100, 1024, b"abcd")
        assert pic1 == pic2  # metadata mismatch details and file modification timestamp don't count

        assert pic1 != Picture(PictureType.COVER_FRONT, "image/png", 100, 100, 1024, b"ffff")
        assert pic1 != Picture(PictureType.COVER_BACK, "image/png", 100, 100, 1024, b"abcd")
        assert pic1 != Picture(PictureType.COVER_FRONT, "image/png", 100, 100, 0, b"abcd")

    def test_get_picture_metadata(self):
        image_data = make_image_data(400, 400, "PNG")
        result = PictureScanner().scan(image_data)
        assert result.picture_info.file_size == len(image_data)
        assert result.picture_info.mime_type == "image/png"
        assert result.picture_info.height == result.picture_info.width == 400
        assert result.picture_info.hash == xxhash.xxh32_digest(image_data)
        assert result.load_issue == ()

    def test_get_picture_metadata_error(self):
        image_data = b"not an image file"
        result = PictureScanner().scan(image_data)
        assert result.picture_info.file_size == len(image_data)
        assert result.picture_info.mime_type == ""
        assert result.picture_info.height == result.picture_info.width == 0
        assert result.picture_info.hash == xxhash.xxh32_digest(image_data)
        assert result.load_issue == (("error", "cannot identify image file"),)

    def test_get_picture_metadata_cache(self, mocker):
        image_data = make_image_data(400, 400, "PNG")
        pic_info = PictureInfo("image/png", 400, 400, 24, 1024, b"1234")
        scanner = PictureScanner()
        get_picture_info_mock = mocker.patch("albums.tagger.picture.get_picture_info", return_value=(pic_info, None))
        result1 = scanner.scan(image_data)
        assert get_picture_info_mock.call_count == 1
        result2 = scanner.scan(image_data)
        assert get_picture_info_mock.call_count == 1
        assert result1 == result2
