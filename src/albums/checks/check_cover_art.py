from collections import defaultdict
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
        if album.codec() != "FLAC" and self.cover_front_required:
            # reading embedded images is only supported for FLAC files, but image files in folder can be examined
            return None

        tracks_with_cover = 0
        issues: set[str] = set()
        album_art = [(True, track.pictures) for track in album.tracks]
        album_art.extend([(False, [picture]) for picture in album.picture_files.values()])
        pictures_by_type: defaultdict[PictureType, list[Picture]] = defaultdict(list)

        for embedded, pictures in album_art:
            file_cover: Picture | None = None
            for picture in pictures:
                pictures_by_type[picture.picture_type].append(picture)
                if picture.picture_type == PictureType.COVER_FRONT:
                    if file_cover is None:
                        file_cover = picture
                    else:
                        issues.add("multiple COVER_FRONT pictures in one track")
                if embedded:
                    if picture.mismatch:
                        actual = f"{picture.format} {picture.width}x{picture.height}"
                        reported = f"{picture.mismatch.get('format', picture.format)} {picture.mismatch.get('width', picture.width)}x{picture.mismatch.get('height', picture.height)}"
                        issues.add(f"embedded image metadata mismatch, actual {actual} but container says {reported}")
                    if picture.format not in {"image/png", "image/jpeg"}:
                        issues.add(f"embedded image {picture.picture_type.name} is not a recommended format ({picture.format})")
            if embedded:
                if file_cover:
                    tracks_with_cover += 1

        front_covers = pictures_by_type.get(PictureType.COVER_FRONT)
        if front_covers:
            if tracks_with_cover and tracks_with_cover != len(album.tracks):
                issues.add("some tracks have COVER_FRONT and some do not")

            unique_front_covers = set(front_covers)
            if len(unique_front_covers) != 1:
                issues.add("COVER_FRONT pictures are not all the same")

            for cover in unique_front_covers:
                if cover.width != cover.height:
                    issues.add(f"COVER_FRONT is not square ({cover.width}x{cover.height})")
                if min(cover.height, cover.width) < self.min_pixels:
                    issues.add(f"COVER_FRONT image is too small ({cover.width}x{cover.height})")
                if max(cover.height, cover.width) > self.max_pixels:
                    issues.add(f"COVER_FRONT image is too large ({cover.width}x{cover.height})")
        elif pictures_by_type:
            issues.add("album has pictures but none is COVER_FRONT picture")
        elif self.cover_front_required:
            issues.add("album does not have a COVER_FRONT picture")

        if issues:
            return CheckResult(ProblemCategory.PICTURES, ", ".join(list(issues)))
