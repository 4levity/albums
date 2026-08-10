"""Picture information types and utilities for extracting metadata from image data."""

import base64
import io
import mimetypes
from dataclasses import dataclass
from typing import Any, Tuple

from PIL import Image

from .format import format_to_mime_type, get_depth_bpp

# Calling mimetypes.init early prevents mimetypes.guess_type(".pcx") from failing with certain test run ordering
# and specifying files=[] may avoid OS-specific bugs.
mimetypes.init(files=[])


# Type representing any issues encountered when loading image data.
type LoadIssuesType = Tuple[Tuple[str, str | int], ...]


@dataclass(frozen=True)
class PictureInfo:
    """Metadata about an embedded or external picture used as album artwork.

    Attributes:
        mime_type: MIME type of the image data (e.g. ``"image/jpeg"``).
        width: Image width in pixels, or 0 if unavailable.
        height: Image height in pixels, or 0 if unavailable.
        depth_bpp: Color depth in bits-per-pixel, or 0 if unavailable.
        file_size: Size of the image data in bytes.
        file_hash: xxHash-32 fingerprint of the image content for deduplication.
        load_issue: Tuple of (category, message) describing any errors loading the image. Empty when valid.
    """

    mime_type: str
    width: int
    height: int
    depth_bpp: int
    file_size: int
    file_hash: bytes  # xxhash.xxh32_digest(image_data)
    load_issue: LoadIssuesType = ()

    def to_dict(self) -> dict[str, Any | str]:
        """Return a JSON-serializable dictionary of the picture metadata.

        Returns:
            A dict with keys ``mime_type``, ``width``, ``height``, ``depth_bpp``, ``file_size``,
            ``file_hash`` (base64-encoded), and optionally ``load_issue``.
        """
        result = self.__dict__ | {"file_hash": base64.b64encode(self.file_hash).decode()}
        if not self.load_issue:
            del result["load_issue"]
        return result


def get_picture_info(image_data: bytes, file_hash: bytes) -> PictureInfo:
    """Extract metadata from raw image bytes using Pillow.

    Args:
        image_data: Raw binary content of the image to analyze.
        file_hash: Precomputed xxHash fingerprint of *image_data*.

    Returns:
        A ``PictureInfo`` describing the loaded image, with any load warnings/errors recorded in ``load_issue``.
    """
    file_size = len(image_data)

    image = Image.open(io.BytesIO(image_data))
    image.load()  # fully load image to ensure it is loadable
    mime_type: str | None = None
    if image.format:
        mime_type = format_to_mime_type(image.format)
    depth_bpp = get_depth_bpp(image.mode)

    return PictureInfo(
        mime_type if mime_type else "",
        image.width,
        image.height,
        depth_bpp,
        file_size,
        file_hash,
        () if mime_type else (("error", f"couldn't guess MIME type for image format {image.format}"),),
    )
