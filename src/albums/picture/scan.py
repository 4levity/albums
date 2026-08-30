"""Image scanning utilities with caching for fast deduplication of album artwork."""

from typing import Dict, Tuple

import xxhash
from PIL import Image, UnidentifiedImageError

from .info import PictureInfo, get_picture_info

# PictureScannerCache maps a tuple of ``(file_size, file_hash)`` to ``PictureInfo``.
type PictureScannerCache = Dict[Tuple[int, bytes], PictureInfo]


class PictureScanner:
    """Scan raw image data to extract metadata, with an in-memory cache keyed by size and hash.

    Use this class when scanning many images to avoid redundant Pillow parsing of identical content.
    The constructor accepts a pre-populated cache (e.g. loaded from the database) to further skip work.
    """

    _cache: PictureScannerCache

    def __init__(self, preload_cache: PictureScannerCache = {}):
        """Initialize the scanner, optionally seeding it with a pre-populated cache.

        Args:
            preload_cache: Existing ``PictureInfo`` records keyed by ``(file_size, file_hash)``.
                          Entries are normalized to retain only error-level issues so stale warnings
                          from prior scans do not surface in newly-verified metadata.
        """
        self._cache = dict(
            (
                pic_key,
                info
                if (len(info.load_issue) == 0 or (len(info.load_issue) == 1 and info.load_issue[0][0] == "error"))
                else PictureInfo(
                    info.mime_type,
                    info.width,
                    info.height,
                    info.depth_bpp,
                    info.file_size,
                    info.file_hash,
                    tuple((k, v) for k, v in info.load_issue if k == "error"),
                ),
            )
            for pic_key, info in preload_cache.items()
        )

    def scan(
        self,
        image_data: bytes,
        expect_mime_type: str | None = None,
        expect_width: int | None = None,
        expect_height: int | None = None,
    ) -> PictureInfo:
        """Scan *image_data* and return its ``PictureInfo``, populating cache on first use.

        If any of the ``expect_`` parameters are provided non-``None`` values, the returned
        ``PictureInfo`` will contain ``mismatch`` entries in ``load_issue`` when actual metadata
        differs from expectations.

        Args:
            image_data: Raw binary bytes of the image to analyze.
            expect_mime_type: Expected MIME type.
            expect_width: Expected width in pixels.
            expect_height: Expected height in pixels.

        Returns:
            A ``PictureInfo`` describing the scanned image, potentially augmented with mismatch notes.
        """
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
