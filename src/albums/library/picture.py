import io
import logging
import mimetypes
from pathlib import Path

import humanize
import xxhash
from PIL import Image, UnidentifiedImageError
from PIL.ImageFile import ImageFile

from ..types import Picture, PictureType

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_SUFFIXES = [".png", ".jpg", ".jpeg", ".gif"]
MAX_IMAGE_SIZE = 64 * 1024 * 1024  # don't load and scan image files larger than this. 16 MB is the max for ID3v2 and FLAC tags.
IMAGE_MODE_BPP = {"RGB": 24, "RGBA": 32, "CMYK": 32, "YCbCr": 24, "I;16": 16, "I;16B": 16, "I;16L": 16, "I": 32, "F": 32, "1": 1}


def picture_from_path(file: Path) -> Picture | None:
    stat = file.stat()
    if stat.st_size > MAX_IMAGE_SIZE:
        logger.warning(
            f"skipping image file {str(file)} because it is {humanize.naturalsize(stat.st_size, binary=True)} (albums max = {humanize.naturalsize(MAX_IMAGE_SIZE, binary=True)})"
        )
        # TODO: record the existence of the large image even if we do not load its metadata, just like we would with a load error
        return None
    with open(file, "rb") as f:
        image_data = f.read()
    picture_type = picture_type_from_filename(file.name)
    picture = get_picture_metadata(image_data, picture_type)  # may or may not load successfully
    picture.modify_timestamp = int(stat.st_mtime)
    return picture


def picture_type_from_filename(filename: str) -> PictureType:
    filename_lower = str.lower(filename)
    for match in ["folder", ".folder", "cover", "album", "thumbnail"]:
        if filename_lower.startswith(match):
            return PictureType.COVER_FRONT
    return PictureType.OTHER


def get_image(image_data: bytes) -> tuple[ImageFile, str] | str:
    try:
        image = Image.open(io.BytesIO(image_data))
        mimetype: str | None = None
        if image.format:
            mimetype, _ = mimetypes.guess_type(f"_.{image.format}")
        if not mimetype:
            # we don't use container-specified MIME type except to note if it is wrong
            return f"couldn't guess MIME type for image format {image.format}"
        return (image, mimetype)
    except UnidentifiedImageError as ex:
        return repr(ex)


def get_picture_metadata(image_data: bytes, picture_type: PictureType):
    file_size = len(image_data)
    xhash = xxhash.xxh32_digest(image_data)
    image_info = get_image(image_data)
    if isinstance(image_info, str):
        return Picture(picture_type, "Unknown", 0, 0, file_size, xhash, {"error": image_info})
    else:
        (image, mimetype) = image_info
        return Picture(picture_type, mimetype, image.width, image.height, file_size, xhash)
