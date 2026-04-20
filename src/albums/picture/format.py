import mimetypes
from typing import Final, Mapping

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


def get_depth_bpp(pillow_mode: str, guess: int = 24):
    if pillow_mode in IMAGE_MODE_BPP:
        return IMAGE_MODE_BPP[pillow_mode]
    return guess


MIME_PILLOW_FORMAT: Final[Mapping[str, str]] = {
    "image/bmp": "BMP",
    "image/gif": "GIF",
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/tiff": "TIFF",
    "image/vnd.zbrush.pcx": "PCX",
    "image/webp": "WEBP",
}
PILLOW_FORMAT_MIME: Final[Mapping[str, str]] = dict((pillow, mime) for mime, pillow in MIME_PILLOW_FORMAT.items())

# Can add any extension if format is autodetected by Pillow and ".<FORMAT>" is a file extension supported by mimetypes.guess_type
SUPPORTED_IMAGE_SUFFIXES: Final = frozenset({".bmp", ".gif", ".jpeg", ".jpg", ".pcx", ".png", ".tif", ".tiff", ".webp"})
SUPPORTED_IMAGE_MIME_TYPES: Final = frozenset(MIME_PILLOW_FORMAT.keys())


def mime_type_to_format(mime_type: str) -> str:
    return MIME_PILLOW_FORMAT[mime_type]


def format_to_mime_type(image_format: str) -> str:
    mime_type, _ = mimetypes.guess_type(f"_.{image_format}")
    return mime_type or PILLOW_FORMAT_MIME[str.upper(image_format)]
