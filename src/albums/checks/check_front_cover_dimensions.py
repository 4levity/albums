import logging
from typing import Any

from ..types import Album, CheckResult, Picture, PictureType, ProblemCategory
from .base_check import Check

logger = logging.getLogger(__name__)


class CheckFrontCoverDimensions(Check):
    name = "front_cover_dimensions"
    default_config = {
        "enabled": True,
        "min_pixels": 100,
        "max_pixels": 4096,
        "squareness": 0.98,
    }
    must_pass_checks = {"front_cover_selection"}  # either all the COVER_FRONT images are the same or there is a front_cover_source selected

    def init(self, check_config: dict[str, Any]):
        self.min_pixels = int(check_config.get("min_pixels", CheckFrontCoverDimensions.default_config["min_pixels"]))
        self.max_pixels = int(check_config.get("max_pixels", CheckFrontCoverDimensions.default_config["max_pixels"]))
        self.squareness = float(check_config.get("squareness", CheckFrontCoverDimensions.default_config["squareness"]))

    def check(self, album: Album) -> CheckResult | None:
        issues: set[str] = set()
        embedded_covers: dict[Picture, str] = {}
        for track in album.tracks:
            covers = [pic for pic in track.pictures if pic.picture_type == PictureType.COVER_FRONT]
            if covers:
                embedded_covers[covers[0]] = track.filename
        cover_files = [(pic, filename) for filename, pic in album.picture_files.items() if pic.picture_type == PictureType.COVER_FRONT]

        # because front_cover_selection must pass, either there is no cover, all cover images are the same, or one file is front_cover_source
        # but double check anyways
        if len(cover_files) > 1:
            return CheckResult(ProblemCategory.PICTURES, "there is more than one front cover image file (problem with front_cover_selection?)")
        file_cover = cover_files[0][0] if cover_files else None
        if len(embedded_covers) > 1:
            return CheckResult(
                ProblemCategory.PICTURES, "there is more than one unique embedded cover image file (problem with front_cover_selection?)"
            )
        embedded_cover = list(embedded_covers.items())[0][0] if embedded_covers else None
        if file_cover and embedded_cover and not file_cover.front_cover_source and file_cover != embedded_cover:
            return CheckResult(
                ProblemCategory.PICTURES,
                "cover image file is different than em# thbedded but not marked as front_cover_source (problem with front_cover_selection?)",
            )

        if file_cover:  # either front_cover_source or identical to embedded images
            (cover, _from_file) = cover_files[0]
        elif embedded_cover:
            (cover, _from_file) = list(embedded_covers.items())[0]
        else:
            return None  # no cover means front_cover_selection is not configured to require one

        if not self._cover_square_enough(cover.width, cover.height):
            # TODO: squarify
            issues.add(f"COVER_FRONT is not square ({cover.width}x{cover.height})")
        if min(cover.height, cover.width) < self.min_pixels:
            # TODO: fix if there is a higher resolution cover source available
            issues.add(f"COVER_FRONT image is too small ({cover.width}x{cover.height})")
        if max(cover.height, cover.width) > self.max_pixels:
            # TODO: extract original to file, then resize/compress
            issues.add(f"COVER_FRONT image is too large ({cover.width}x{cover.height})")

        if issues:
            return CheckResult(ProblemCategory.PICTURES, ", ".join(list(issues)))

    def _cover_square_enough(self, x: int, y: int) -> bool:
        aspect = 0 if max(x, y) == 0 else min(x, y) / max(x, y)
        return aspect >= self.squareness
