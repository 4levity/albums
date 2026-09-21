from pathlib import Path

from PIL import Image

from albums.app import Context
from albums.interactive import render_image_table
from albums.picture import PictureInfo
from albums.tagger import AlbumTagger, Picture, PictureType


def _picture() -> Picture:
    return Picture(
        picture_info=PictureInfo("image/png", 400, 400, 24, 1024, b""),
        type=PictureType.COVER_FRONT,
        description="",
    )


def test_render_image_table_repeated_calls():
    # render more than once: the first call runs render_image_table's deferred imports, later calls reuse them
    pictures = [
        (_picture(), Image.new("RGB", (400, 400)), b"1"),
        (_picture(), Image.new("RGB", (400, 400)), b"2"),
    ]
    for _ in range(2):
        table = render_image_table(Context(), AlbumTagger(Path("album")), pictures, {})
        assert table
