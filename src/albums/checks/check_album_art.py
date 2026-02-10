import logging
from collections import defaultdict
from typing import Any

import humanize

from ..types import Album, Picture, PictureType
from .base_check import Check, CheckResult, ProblemCategory

logger = logging.getLogger(__name__)


class CheckAlbumArt(Check):
    name = "album_art"
    default_config = {
        "enabled": True,
        "cover_min_pixels": 100,
        "cover_max_pixels": 2048,
        "cover_squareness": 0.98,
        "embedded_size_max": 8 * 1024 * 1024,  # up to 16 MB is OK in ID3v2
    }

    def init(self, check_config: dict[str, Any]):
        self.cover_min_pixels = int(check_config.get("cover_min_pixels", CheckAlbumArt.default_config["cover_min_pixels"]))
        self.cover_max_pixels = int(check_config.get("cover_max_pixels", CheckAlbumArt.default_config["cover_max_pixels"]))
        self.cover_squareness = float(check_config.get("cover_squareness", CheckAlbumArt.default_config["cover_squareness"]))
        self.embedded_size_max = int(check_config.get("embedded_size_max", CheckAlbumArt.default_config["embedded_size_max"]))

    def check(self, album: Album) -> CheckResult | None:
        issues: set[str] = set()
        album_art = [(track.filename, True, track.pictures) for track in album.tracks]
        album_art.extend([(filename, False, [picture]) for filename, picture in album.picture_files.items()])

        pictures_by_type: defaultdict[PictureType, set[Picture]] = defaultdict(set)
        picture_sources: defaultdict[Picture, list[tuple[str, bool]]] = defaultdict(list)
        for filename, embedded, pictures in album_art:
            for picture in pictures:
                picture_sources[picture].append((filename, embedded))
                pictures_by_type[picture.picture_type].add(picture)
                if embedded:
                    if picture.format not in {"image/png", "image/jpeg"}:
                        issues.add(f"embedded image {picture.picture_type.name} is not a recommended format ({picture.format})")
                    if picture.file_size > self.embedded_size_max:
                        file_size = humanize.naturalsize(picture.file_size, binary=True)
                        file_size_max = humanize.naturalsize(self.embedded_size_max, binary=True)
                        issues.add(f"embedded image {picture.picture_type.name} is over the configured limit ({file_size} > {file_size_max})")

        front_covers = pictures_by_type.get(PictureType.COVER_FRONT)
        if front_covers:
            for cover in front_covers:
                if not self._cover_square_enough(cover.width, cover.height):
                    issues.add(f"COVER_FRONT is not square ({cover.width}x{cover.height})")
                if min(cover.height, cover.width) < self.cover_min_pixels:
                    issues.add(f"COVER_FRONT image is too small ({cover.width}x{cover.height})")
                if max(cover.height, cover.width) > self.cover_max_pixels:
                    issues.add(f"COVER_FRONT image is too large ({cover.width}x{cover.height})")

        if issues:
            return CheckResult(ProblemCategory.PICTURES, ", ".join(list(issues)))

    def _cover_square_enough(self, x: int, y: int) -> bool:
        aspect = 0 if max(x, y) == 0 else min(x, y) / max(x, y)
        return aspect >= self.cover_squareness
