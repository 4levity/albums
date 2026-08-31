"""Image format utilities for mapping between MIME types, Pillow formats, and file extensions."""

import mimetypes
from typing import Final, Mapping

# Maps Pillow image mode strings to their corresponding bits-per-pixel depth.
IMAGE_MODE_BPP: Final[Mapping[str, int]] = {
    "1": 1,
    "L": 8,
    "P": 8,
    "RGB": 24,
    "RGBA": 32,
    "CMYK": 32,
    "YCbCr": 24,
    "LAB": 24,
    "HSV": 24,
    "I": 32,
    "F": 32,
    "I;16": 16,
    "I;16B": 16,
    "I;16L": 16,
    "I;16N": 16,
    "LA": 16,
    "PA": 16,
    "RGBX": 32,
}


def get_depth_bpp(pillow_mode: str, guess: int = 24) -> int:
    """Return the bits-per-pixel color depth for a given Pillow image mode.

    Args:
        pillow_mode: The Pillow image mode string (e.g. ``"RGB"``, ``"RGBA"``).
        guess: Default value to return if *pillow_mode* is unrecognized. Defaults to 24.

    Returns:
        The bits-per-pixel depth for *pillow_mode*, or *guess* if mode is unknown.
    """
    if pillow_mode in IMAGE_MODE_BPP:
        return IMAGE_MODE_BPP[pillow_mode]
    return guess


# Maps MIME image types to their corresponding Pillow format names.
MIME_PILLOW_FORMAT: Final[Mapping[str, str]] = {
    "image/bmp": "BMP",
    "image/gif": "GIF",
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/tiff": "TIFF",
    "image/vnd.zbrush.pcx": "PCX",
    "image/webp": "WEBP",
}

# Reverse of ``MIME_PILLOW_FORMAT``: maps Pillow format names to MIME image types.
PILLOW_FORMAT_MIME: Final[Mapping[str, str]] = dict((pillow, mime) for mime, pillow in MIME_PILLOW_FORMAT.items())


# File extensions supported as source images for embedding/processing.
# New formats can be added if Pillow autodetects them and mimetypes.guess_type recognizes the extension.
SUPPORTED_IMAGE_SUFFIXES: Final = frozenset({".bmp", ".gif", ".jpeg", ".jpg", ".pcx", ".png", ".tif", ".tiff", ".webp"})

# MIME types supported as source images for embedding/processing.
SUPPORTED_IMAGE_MIME_TYPES: Final = frozenset(MIME_PILLOW_FORMAT.keys())


def mime_type_to_format(mime_type: str) -> str:
    """Convert a MIME image type to its Pillow format name.

    Args:
        mime_type: A MIME type string (e.g. ``"image/jpeg"``).

    Returns:
        The corresponding Pillow format name (e.g. ``"JPEG"``).
    """
    return MIME_PILLOW_FORMAT[mime_type]


def format_to_mime_type(image_format: str) -> str | None:
    """Convert a Pillow format name to its MIME image type.

    Args:
        image_format: A Pillow format name (e.g. ``"JPEG"``).

    Returns:
        The corresponding MIME type string (e.g. ``"image/jpeg"``), or ``None`` if no
        MIME type is known for *image_format* (e.g. ``"TGA"``, ``"QOI"`` or ``"DDS"``).
    """
    mime_type, _ = mimetypes.guess_type(f"_.{image_format}")
    if mime_type:
        return mime_type
    return PILLOW_FORMAT_MIME.get(str.upper(image_format))
