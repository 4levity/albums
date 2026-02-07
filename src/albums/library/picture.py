import io
import logging
import mimetypes

import xxhash
from PIL import Image

from ..types import Picture, PictureType

logger = logging.getLogger(__name__)


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
