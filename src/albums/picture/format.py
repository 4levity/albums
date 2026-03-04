IMAGE_MODE_BPP = {
    "1": 1,
    "CMYK": 32,
    "F": 32,
    "I": 32,
    "I;16": 16,
    "I;16B": 16,
    "I;16L": 16,
    "P": 8,
    "RGB": 24,
    "RGBA": 32,
    "YCbCr": 24,
}

MIME_PILLOW_FORMAT = {
    "image/bmp": "BMP",
    "image/gif": "GIF",
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/tiff": "TIFF",
    "image/vnd.zbrush.pcx": "PCX",
    "image/webp": "WEBP",
}

# Can add any extension if format is autodetected by Pillow and ".<FORMAT>" is a file extension supported by mimetypes.guess_type
SUPPORTED_IMAGE_SUFFIXES = frozenset({".bmp", ".gif", ".jpeg", ".jpg", ".pcx", ".png", ".tif", ".tiff", ".webp"})
