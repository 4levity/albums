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


type LoadIssuesType = Tuple[Tuple[str, str | int], ...]


@dataclass(frozen=True)
class PictureInfo:
    mime_type: str
    width: int
    height: int
    depth_bpp: int
    file_size: int
    file_hash: bytes  # xxhash.xxh32_digest(image_data)
    load_issue: LoadIssuesType = ()

    def to_dict(self):
        result = self.__dict__ | {"file_hash": base64.b64encode(self.file_hash).decode()}
        if not self.load_issue:
            del result["load_issue"]
        return result


def get_picture_info(image_data: bytes, file_hash: bytes) -> PictureInfo:
    image = Image.open(io.BytesIO(image_data))
    image.load()  # fully load image to ensure it is loadable
    depth_bpp = IMAGE_MODE_BPP.get(image.mode, 0)
    file_size = len(image_data)

    mime_type: str | None = None
    if image.format:
        mime_type, _ = mimetypes.guess_type(f"_.{image.format}")

    return PictureInfo(
        mime_type if mime_type else "",
        image.width,
        image.height,
        depth_bpp,
        file_size,
        file_hash,
        () if mime_type else (("error", f"couldn't guess MIME type for image format {image.format}"),),
    )
