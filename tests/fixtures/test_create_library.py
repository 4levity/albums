import io

from PIL import Image

from .create_library import create_picture_file, make_image_data


class TestMakeImageData:
    def test_default(self):
        data = make_image_data()
        with Image.open(io.BytesIO(data)) as image:
            assert image.size == (400, 400)
            assert image.getpixel((0, 0)) == (0, 0, 255)  # blue

    def test_color_and_size(self):
        # "green" is the CSS web color (0, 128, 0), not pure green
        for color, expected in (("red", (255, 0, 0)), ("green", (0, 128, 0))):
            data = make_image_data(32, 48, "PNG", color)
            with Image.open(io.BytesIO(data)) as image:
                assert image.size == (32, 48)
                assert image.getpixel((0, 0)) == expected
                assert image.getpixel((31, 47)) == expected

    def test_jpeg(self):
        # JPEG is lossy, so allow some color drift
        data = make_image_data(20, 20, "JPEG", "red")
        with Image.open(io.BytesIO(data)) as image:
            pixel = image.getpixel((10, 10))
            assert isinstance(pixel, tuple)
            (r, g, b) = pixel
            assert r > 200
            assert g < 50
            assert b < 50


class TestCreatePictureFile:
    def test_color_and_size(self, tmp_path):
        path = tmp_path / "picture.png"
        create_picture_file(path, 16, 16, "red")
        with Image.open(path) as image:
            assert image.size == (16, 16)
            assert image.getpixel((0, 0)) == (255, 0, 0)
