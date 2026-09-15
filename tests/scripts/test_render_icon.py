import shutil
from pathlib import Path

from PIL import Image

from scripts import render_icon

SOURCE = Path(__file__).resolve().parents[2] / "docs" / "art" / "icon.png"


class TestRenderPng:
    def test_renders_square_png(self, tmp_path):
        destination = tmp_path / "favicon.png"
        render_icon.render_png(SOURCE, destination, render_icon.FAVICON_SIZE)
        with Image.open(destination) as img:
            assert img.format == "PNG"
            assert img.size == (render_icon.FAVICON_SIZE, render_icon.FAVICON_SIZE)


class TestRenderIco:
    def test_renders_ico_sizes(self, tmp_path):
        destination = tmp_path / "icon.ico"
        render_icon.render_ico(SOURCE, destination, render_icon.ICO_SIZES)
        with Image.open(destination) as img:
            assert img.format == "ICO"
            assert img.info["sizes"] == {(size, size) for size in render_icon.ICO_SIZES}


class TestMain:
    def test_writes_derived_images(self, monkeypatch, tmp_path):
        art = tmp_path / "docs" / "art"
        art.mkdir(parents=True)
        shutil.copy(SOURCE, art / "icon.png")
        monkeypatch.chdir(tmp_path)
        assert render_icon.main() == 0
        for name, size in [(render_icon.FAVICON, render_icon.FAVICON_SIZE), (render_icon.LOGO, render_icon.LOGO_SIZE)]:
            with Image.open(tmp_path / name) as img:
                assert img.format == "PNG"
                assert img.size == (size, size)
        with Image.open(tmp_path / render_icon.ICO) as img:
            assert img.format == "ICO"
            assert img.info["sizes"] == {(size, size) for size in render_icon.ICO_SIZES}

    def test_fails_without_master_icon(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        assert render_icon.main() == 1
