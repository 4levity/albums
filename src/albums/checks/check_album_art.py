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
        "cover_front_required": False,
        "cover_min_pixels": 100,
        "cover_max_pixels": 2048,
        "cover_unique": True,
        "cover_squareness": 0.98,
        "embedded_size_max": 8 * 1024 * 1024,  # up to 16 MB is OK in ID3v2
    }

    def init(self, check_config: dict[str, Any]):
        self.cover_front_required = bool(check_config.get("cover_front_required", CheckAlbumArt.default_config["cover_front_required"]))
        self.cover_min_pixels = int(check_config.get("cover_min_pixels", CheckAlbumArt.default_config["cover_min_pixels"]))
        self.cover_max_pixels = int(check_config.get("cover_max_pixels", CheckAlbumArt.default_config["cover_max_pixels"]))
        self.cover_unique = bool(check_config.get("cover_unique", CheckAlbumArt.default_config["cover_unique"]))
        self.cover_squareness = float(check_config.get("cover_squareness", CheckAlbumArt.default_config["cover_squareness"]))
        self.embedded_size_max = int(check_config.get("embedded_size_max", CheckAlbumArt.default_config["embedded_size_max"]))

    def check(self, album: Album) -> CheckResult | None:
        if album.codec() != "FLAC" and self.cover_front_required:
            # reading embedded images is only supported for FLAC files, but image files in folder can be examined
            return None

        tracks_with_cover = 0
        issues: set[str] = set()
        album_art = [(True, track.pictures) for track in album.tracks]
        album_art.extend([(False, [picture]) for picture in album.picture_files.values()])

        pictures_by_type: defaultdict[PictureType, set[Picture]] = defaultdict(set)
        for embedded, pictures in album_art:
            file_cover: Picture | None = None
            for picture in pictures:
                pictures_by_type[picture.picture_type].add(picture)
                if picture.picture_type == PictureType.COVER_FRONT:
                    if file_cover is None:
                        file_cover = picture
                    elif file_cover == picture:
                        issues.add("duplicate COVER_FRONT pictures in one track")
                    else:
                        issues.add("multiple COVER_FRONT pictures in one track")
                if embedded:
                    if picture.format not in {"image/png", "image/jpeg"}:
                        issues.add(f"embedded image {picture.picture_type.name} is not a recommended format ({picture.format})")
                    if picture.file_size > self.embedded_size_max:
                        file_size = humanize.naturalsize(picture.file_size, binary=True)
                        file_size_max = humanize.naturalsize(self.embedded_size_max, binary=True)
                        issues.add(f"embedded image {picture.picture_type.name} is over the configured limit ({file_size} > {file_size_max})")
            if embedded:
                if file_cover:
                    tracks_with_cover += 1

        front_covers = pictures_by_type.get(PictureType.COVER_FRONT)
        if front_covers:
            if tracks_with_cover and tracks_with_cover != len(album.tracks):
                issues.add("some tracks have COVER_FRONT and some do not")

            if self.cover_unique and len(front_covers) != 1:
                issues.add("COVER_FRONT pictures are not all the same")

            for cover in front_covers:
                if not self._cover_square_enough(cover.width, cover.height):
                    issues.add(f"COVER_FRONT is not square ({cover.width}x{cover.height})")
                if min(cover.height, cover.width) < self.cover_min_pixels:
                    issues.add(f"COVER_FRONT image is too small ({cover.width}x{cover.height})")
                if max(cover.height, cover.width) > self.cover_max_pixels:
                    issues.add(f"COVER_FRONT image is too large ({cover.width}x{cover.height})")
        elif pictures_by_type:
            issues.add("album has pictures but none is COVER_FRONT picture")
        elif self.cover_front_required:
            issues.add("album does not have a COVER_FRONT picture")

        if issues:
            return CheckResult(ProblemCategory.PICTURES, ", ".join(list(issues)))

    def _cover_square_enough(self, x: int, y: int) -> bool:
        aspect = 0 if max(x, y) == 0 else min(x, y) / max(x, y)
        return aspect >= self.cover_squareness
