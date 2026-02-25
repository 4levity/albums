# type PictureCache = Dict[Tuple[int, bytes], EmbeddedPicture]

import io
import mimetypes
from dataclasses import dataclass
from typing import Dict, Tuple

import xxhash
from PIL import Image, UnidentifiedImageError

from .types import PictureInfo

IMAGE_MODE_BPP = {"RGB": 24, "RGBA": 32, "CMYK": 32, "YCbCr": 24, "I;16": 16, "I;16B": 16, "I;16L": 16, "I": 32, "F": 32, "L": 8, "1": 1}


@dataclass(frozen=True)
class PictureScanResult:
    picture_info: PictureInfo
    load_issue: Tuple[Tuple[str, str | int], ...]


class PictureScanner:
    _cache: Dict[Tuple[int, bytes], Tuple[PictureInfo, str | None]] = {}

    def scan(
        self, image_data: bytes, expect_mime_type: str | None = None, expect_width: int | None = None, expect_height: int | None = None
    ) -> PictureScanResult:
        file_size = len(image_data)
        hash = xxhash.xxh32_digest(image_data)
        key = (file_size, hash)
        if key not in self._cache:
            try:
                image = Image.open(io.BytesIO(image_data))
                image.load()  # fully load image to ensure it is loadable
                mime_type: str | None = None
                if image.format:
                    mime_type, _ = mimetypes.guess_type(f"_.{image.format}")
                depth_bpp = IMAGE_MODE_BPP.get(image.mode, 0)
                if mime_type:
                    picture_info = PictureInfo(mime_type, image.width, image.height, depth_bpp, file_size, hash)
                    self._cache[key] = (picture_info, None)
                else:
                    picture_info = PictureInfo("unknown", image.width, image.height, depth_bpp, file_size, hash)
                    self._cache[key] = (picture_info, f"couldn't guess MIME type for image format {image.format}")

            except (IOError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as ex:
                exception_description = repr(ex)
                error = "cannot identify image file" if "cannot identify image file" in exception_description else exception_description
                self._cache[key] = (PictureInfo("", 0, 0, 0, file_size, hash), error)

        (picture_info, error) = self._cache[key]
        issues: Tuple[Tuple[str, str | int], ...]
        if error:
            issues = (("error", error),)
        else:
            issues = (("format", expect_mime_type),) if (expect_mime_type and picture_info.mime_type != expect_mime_type) else ()
            issues = issues + ((("width", expect_width),) if (expect_width is not None and picture_info.width != expect_width) else ())
            issues = issues + ((("height", expect_height),) if (expect_height is not None and picture_info.height != expect_height) else ())
        return PictureScanResult(picture_info, issues)
