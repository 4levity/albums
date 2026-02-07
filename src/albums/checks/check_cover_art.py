from typing import Any

from ..types import Album, Picture, PictureType
from .base_check import Check, CheckResult, ProblemCategory


class CheckCoverArt(Check):
    name = "cover_art"
    default_config = {"enabled": True, "cover_front_required": False, "min_pixels": 100, "max_pixels": 2048}

    def init(self, check_config: dict[str, Any]):
        self.cover_front_required = bool(check_config.get("cover_front_required", CheckCoverArt.default_config["cover_front_required"]))
        self.min_pixels = int(check_config.get("min_pixels", CheckCoverArt.default_config["min_pixels"]))
        self.max_pixels = int(check_config.get("max_pixels", CheckCoverArt.default_config["max_pixels"]))

    def check(self, album: Album) -> CheckResult | None:
        if album.codec() != "FLAC":
            # only supported for FLAC files currently
            return None

        album_cover: Picture | None = None
        tracks_with_cover = 0
        issues: set[str] = set()
        for track in album.tracks:
            track_cover: Picture | None = None
            for picture in track.pictures:
                if picture.picture_type == PictureType.COVER_FRONT:
                    if track_cover is None:
                        tracks_with_cover += 1
                        track_cover = picture
                    else:
                        issues.add("multiple COVER_FRONT pictures in one track")
                if picture.mismatch:
                    actual = f"{picture.format} {picture.width}x{picture.height}"
                    reported = f"{picture.mismatch.get('format', picture.format)} {picture.mismatch.get('width', picture.width)}x{picture.mismatch.get('height', picture.height)}"
                    issues.add(f"embedded image metadata mismatch, actual {actual} but container says {reported}")

            if track_cover and not album_cover:
                album_cover = track_cover
            elif track_cover and track_cover != album_cover:
                issues.add("COVER_FRONT pictures are not all the same")
            elif track_cover:
                tracks_with_cover += 1

            if len(track.pictures) and not album_cover:
                issues.add("track has pictures but none is COVER_FRONT picture")
        if album_cover and tracks_with_cover < len(album.tracks):
            issues.add("some tracks have COVER_FRONT and some do not")

        if album_cover:
            if album_cover.width != album_cover.height:
                issues.add(f"COVER_FRONT is not square ({album_cover.width}x{album_cover.height})")
            if album_cover.format not in {"image/png", "image/jpeg"}:
                issues.add(f"COVER_FRONT image is not a recommended format ({album_cover.format})")
            if min(album_cover.height, album_cover.width) < self.min_pixels:
                issues.add(f"COVER_FRONT image is too small ({album_cover.width}x{album_cover.height})")
            if max(album_cover.height, album_cover.width) > self.max_pixels:
                issues.add(f"COVER_FRONT image is too large ({album_cover.width}x{album_cover.height})")
        elif self.cover_front_required:
            issues.add("album does not have a COVER_FRONT picture")

        if issues:
            return CheckResult(ProblemCategory.PICTURES, ", ".join(list(issues)))
