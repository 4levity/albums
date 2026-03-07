from typing import Dict, Tuple

import xxhash
from PIL import Image, UnidentifiedImageError

from .info import PictureInfo, get_picture_info


class PictureScanner:
    _cache: Dict[Tuple[int, bytes], PictureInfo]

    def __init__(self):
        self._cache = {}

    def scan(
        self,
        image_data: bytes,
        expect_mime_type: str | None = None,
        expect_width: int | None = None,
        expect_height: int | None = None,
    ) -> PictureInfo:
        hash = xxhash.xxh32_digest(image_data)
        key = (len(image_data), hash)
        if key not in self._cache:
            try:
                self._cache[key] = get_picture_info(image_data, hash)
            except (
                IOError,
                OSError,
                UnidentifiedImageError,
                Image.DecompressionBombError,
            ) as ex:
                exception_description = repr(ex)
                error = "cannot identify image file" if "cannot identify image file" in exception_description else exception_description
                self._cache[key] = PictureInfo("", 0, 0, 0, len(image_data), hash, (("error", error),))

        pic = self._cache[key]
        if not pic.load_issue:
            mismatch = (("format", expect_mime_type),) if (expect_mime_type and pic.mime_type != expect_mime_type) else ()
            mismatch = mismatch + ((("width", expect_width),) if (expect_width is not None and pic.width != expect_width) else ())
            mismatch = mismatch + ((("height", expect_height),) if (expect_height is not None and pic.height != expect_height) else ())
            if mismatch:
                pic = PictureInfo(pic.mime_type, pic.width, pic.height, pic.depth_bpp, pic.file_size, pic.file_hash, mismatch)
        return pic
