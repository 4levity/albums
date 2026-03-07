import xxhash

from albums.picture.format import MIME_PILLOW_FORMAT
from albums.picture.info import PictureInfo
from albums.picture.scan import PictureScanner

from ..fixtures.create_library import make_image_data


class TestPicture:
    def test_scan_size_hash(self):
        image_data = make_image_data(100, 200, "PNG")
        result = PictureScanner().scan(image_data)
        assert result.file_size == len(image_data)
        assert result.file_hash == xxhash.xxh32_digest(image_data)

    def test_scan_png(self):
        image_data = make_image_data(100, 200, MIME_PILLOW_FORMAT["image/png"])
        result = PictureScanner().scan(image_data)
        assert result.load_issue == ()
        assert result.mime_type == "image/png"
        assert result.width == 100
        assert result.height == 200
        assert result.depth_bpp == 24

    def test_scan_jpeg(self):
        image_data = make_image_data(100, 200, MIME_PILLOW_FORMAT["image/jpeg"])
        result = PictureScanner().scan(image_data)
        assert result.load_issue == ()
        assert result.mime_type == "image/jpeg"
        assert result.width == 100
        assert result.height == 200
        assert result.depth_bpp == 24

    def test_scan_gif(self):
        image_data = make_image_data(100, 200, MIME_PILLOW_FORMAT["image/gif"])
        result = PictureScanner().scan(image_data)
        assert result.load_issue == ()
        assert result.mime_type == "image/gif"
        assert result.width == 100
        assert result.height == 200
        assert result.depth_bpp == 8

    def test_scan_bmp(self):
        image_data = make_image_data(100, 200, MIME_PILLOW_FORMAT["image/bmp"])
        result = PictureScanner().scan(image_data)
        assert result.load_issue == ()
        assert result.mime_type == "image/bmp"
        assert result.width == 100
        assert result.height == 200
        assert result.depth_bpp == 24

    def test_scan_pcx(self):
        image_data = make_image_data(100, 200, MIME_PILLOW_FORMAT["image/vnd.zbrush.pcx"])
        result = PictureScanner().scan(image_data)
        assert result.load_issue == ()
        assert result.mime_type == "image/vnd.zbrush.pcx"
        assert result.width == 100
        assert result.height == 200
        assert result.depth_bpp == 24

    def test_scan_tiff(self):
        image_data = make_image_data(100, 200, MIME_PILLOW_FORMAT["image/tiff"])
        result = PictureScanner().scan(image_data)
        assert result.load_issue == ()
        assert result.mime_type == "image/tiff"
        assert result.width == 100
        assert result.height == 200
        assert result.depth_bpp == 24

    def test_scan_webp(self):
        image_data = make_image_data(100, 200, MIME_PILLOW_FORMAT["image/webp"])
        result = PictureScanner().scan(image_data)
        assert result.load_issue == ()
        assert result.mime_type == "image/webp"
        assert result.width == 100
        assert result.height == 200
        assert result.depth_bpp == 24

    def test_get_picture_metadata_error(self):
        image_data = b"not an image file"
        result = PictureScanner().scan(image_data)
        assert result.file_size == len(image_data)
        assert result.mime_type == ""
        assert result.height == result.width == 0
        assert result.file_hash == xxhash.xxh32_digest(image_data)
        assert result.load_issue == (("error", "cannot identify image file"),)

    def test_get_picture_metadata_cache(self, mocker):
        image_data = make_image_data(400, 400, "PNG")
        pic_info = PictureInfo("image/png", 400, 400, 24, 1024, b"1234")
        scanner = PictureScanner()
        get_picture_info_mock = mocker.patch("albums.picture.scan.get_picture_info", return_value=pic_info)
        result1 = scanner.scan(image_data)
        assert get_picture_info_mock.call_count == 1
        result2 = scanner.scan(image_data)
        assert get_picture_info_mock.call_count == 1
        assert result1 == result2
