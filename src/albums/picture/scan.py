from dataclasses import dataclass
from typing import Dict, Tuple

import xxhash
from PIL import Image, UnidentifiedImageError

from .info import PictureInfo, get_picture_info


@dataclass(frozen=True)
class PictureScanResult:
    picture_info: PictureInfo
    load_issue: Tuple[Tuple[str, str | int], ...]


class PictureScanner:
    _cache: Dict[Tuple[int, bytes], Tuple[PictureInfo, str | None]]

    def __init__(self):
        self._cache = {}

    def scan(
        self,
        image_data: bytes,
        expect_mime_type: str | None = None,
        expect_width: int | None = None,
        expect_height: int | None = None,
    ) -> PictureScanResult:
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
                self._cache[key] = (
                    PictureInfo("", 0, 0, 0, len(image_data), hash),
                    error,
                )

        (picture_info, error) = self._cache[key]
        issues: Tuple[Tuple[str, str | int], ...]
        if error:
            issues = (("error", error),)
        else:
            issues = (("format", expect_mime_type),) if (expect_mime_type and picture_info.mime_type != expect_mime_type) else ()
            issues = issues + ((("width", expect_width),) if (expect_width is not None and picture_info.width != expect_width) else ())
            issues = issues + ((("height", expect_height),) if (expect_height is not None and picture_info.height != expect_height) else ())
        return PictureScanResult(picture_info, issues)
