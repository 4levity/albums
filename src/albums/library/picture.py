import io
import mimetypes

import xxhash
from PIL import Image, UnidentifiedImageError
from PIL.ImageFile import ImageFile

from ..types import Picture, PictureType


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
