import io
import logging
import mimetypes
from pathlib import Path

import humanize
import xxhash
from PIL import Image

from ..types import Picture, PictureType

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_SUFFIXES = [".png", ".jpg", ".jpeg", ".gif"]
MAX_IMAGE_SIZE = 64 * 1024 * 1024  # don't load and scan image files larger than this. 16 MB is the max for ID3v2 tags.


def picture_from_path(file: Path) -> Picture | None:
    stat = file.stat()
    if stat.st_size > MAX_IMAGE_SIZE:
        logger.warning(
            f"skipping image file {str(file)} because it is {humanize.naturalsize(stat.st_size, binary=True)} (albums max = {humanize.naturalsize(MAX_IMAGE_SIZE, binary=True)})"
        )
        return None
    with open(file, "rb") as f:
        image_data = f.read()
    picture_type = picture_type_from_filename(file.name)
    picture = get_picture_metadata(image_data, picture_type)
    picture.modify_timestamp = int(stat.st_mtime)
    return picture


def picture_type_from_filename(filename: str) -> PictureType:
    filename_lower = str.lower(filename)
    for match in ["folder", "cover", "album", "thumbnail"]:
        if match in filename_lower:
            return PictureType.COVER_FRONT
    return PictureType.OTHER


def get_picture_metadata(image_data: bytes, picture_type: PictureType):
    file_size = len(image_data)
    xhash = xxhash.xxh32_digest(image_data)
    image = Image.open(io.BytesIO(image_data))
    mimetype: str | None = None
    if image.format:
        mimetype, _ = mimetypes.guess_type(f"_.{image.format}")
    if not mimetype:
        logger.warning(f"couldn't guess MIME type for image format {image.format}")
        mimetype = "Unknown"

    return Picture(picture_type, mimetype, image.width, image.height, file_size, xhash)
