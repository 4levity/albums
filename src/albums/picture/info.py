import base64
import io
import mimetypes
from dataclasses import dataclass
from typing import Tuple

from PIL import Image

from .format import IMAGE_MODE_BPP

# calling mimetimes.init early prevents mimetypes.guess_type(".pcx") from failing with certain test run ordering
# and specifying files=[] may avoid OS-specific bugs:
mimetypes.init(files=[])


@dataclass(frozen=True)
class PictureInfo:
    mime_type: str
    width: int
    height: int
    depth_bpp: int
    file_size: int
    file_hash: bytes  # xxhash.xxh32_digest(image_data)

    def to_dict(self):
        return self.__dict__ | {"file_hash": base64.b64encode(self.file_hash).decode()}


def get_picture_info(image_data: bytes, file_hash: bytes) -> Tuple[PictureInfo, str | None]:
    image = Image.open(io.BytesIO(image_data))
    image.load()  # fully load image to ensure it is loadable
    depth_bpp = IMAGE_MODE_BPP.get(image.mode, 0)
    file_size = len(image_data)

    mime_type: str | None = None
    if image.format:
        mime_type, _ = mimetypes.guess_type(f"_.{image.format}")

    picture_info = PictureInfo(mime_type if mime_type else "unknown", image.width, image.height, depth_bpp, file_size, file_hash)
    if not mime_type:
        return (picture_info, f"couldn't guess MIME type for image format {image.format}")
    return (picture_info, None)
