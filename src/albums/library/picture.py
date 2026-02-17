import io
import mimetypes
from copy import copy
from typing import Dict, Tuple

import xxhash
from PIL import Image, UnidentifiedImageError
from PIL.ImageFile import ImageFile

from ..types import Picture, PictureType

IMAGE_MODE_BPP = {"RGB": 24, "RGBA": 32, "CMYK": 32, "YCbCr": 24, "I;16": 16, "I;16B": 16, "I;16L": 16, "I": 32, "F": 32, "1": 1}


def get_image(image_data: bytes) -> tuple[ImageFile, str] | str:
    try:
        image = Image.open(io.BytesIO(image_data))
        image.load()
        mimetype: str | None = None
        if image.format:
            mimetype, _ = mimetypes.guess_type(f"_.{image.format}")
        if not mimetype:
            # we don't use container-specified MIME type except to note if it is wrong
            return f"couldn't guess MIME type for image format {image.format}"
        return (image, mimetype)
    except (IOError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as ex:
        exception_description = repr(ex)
        return "cannot identify image file" if "cannot identify image file" in exception_description else exception_description


type PictureCache = Dict[Tuple[int, bytes], Picture]


def get_picture_metadata(image_data: bytes, picture_type: PictureType, metadata_cache: PictureCache):
    file_size = len(image_data)
    xhash = xxhash.xxh32_digest(image_data)
    key = (file_size, xhash)
    if key in metadata_cache:
        pic = copy(metadata_cache[key])
        pic.picture_type = picture_type
        return pic

    image_info = get_image(image_data)
    if isinstance(image_info, str):
        pic = Picture(picture_type, "Unknown", 0, 0, file_size, xhash, "", {"error": image_info})
    else:
        (image, mimetype) = image_info
        pic = Picture(picture_type, mimetype, image.width, image.height, file_size, xhash)

    metadata_cache[key] = pic
    return pic
