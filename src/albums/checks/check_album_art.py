import io
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

import humanize
from PIL import Image
from rich.console import RenderableType
from rich.markup import escape
from rich_pixels import Pixels

from albums.library.metadata import get_embedded_image_data

from ..types import Album, Picture, PictureType
from .base_check import Check, CheckResult, Fixer, ProblemCategory

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
        album_art = [(track.filename, True, track.pictures) for track in album.tracks]
        album_art.extend([(filename, False, [picture]) for filename, picture in album.picture_files.items()])

        pictures_by_type: defaultdict[PictureType, set[Picture]] = defaultdict(set)
        picture_sources: defaultdict[Picture, list[tuple[str, bool]]] = defaultdict(list)
        duplicate_in_track = False
        for filename, embedded, pictures in album_art:
            file_cover: Picture | None = None
            for picture in pictures:
                picture_sources[picture].append((filename, embedded))
                pictures_by_type[picture.picture_type].add(picture)
                if picture.picture_type == PictureType.COVER_FRONT:
                    if file_cover is None:
                        file_cover = picture
                    elif file_cover == picture:
                        issues.add("duplicate COVER_FRONT pictures in one track")
                        duplicate_in_track = True
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
        must_select_one = self.cover_unique and front_covers and len(front_covers) > 1
        if front_covers and (must_select_one or duplicate_in_track):
            if must_select_one:
                message = "COVER_FRONT pictures are not all the same"
            else:
                message = "COVER_FRONT picture cleanup needed"
            issues.add(message)

        if front_covers:
            if tracks_with_cover and tracks_with_cover != len(album.tracks):
                issues.add("some tracks have COVER_FRONT and some do not")

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
            if tracks_with_cover:
                candidates: set[Picture] = front_covers if front_covers else set().union(*pictures_by_type.values())  # pyright: ignore[reportUnknownVariableType]
                picture_list = sorted(candidates, key=lambda c: c.file_size, reverse=True)
                options = [self._describe_album_art(picture, picture_sources) for picture in picture_list]
                fixer = Fixer(
                    lambda option: self._select_cover(option, album, picture_list, picture_sources),
                    options,
                    False,
                    None,
                    (options, lambda: self._image_table(album, picture_list, picture_sources)),
                )
            else:
                fixer = None
            return CheckResult(
                ProblemCategory.TAGS,
                ", ".join(list(issues)),
                fixer,
            )
            return CheckResult(ProblemCategory.PICTURES, ", ".join(list(issues)))

    def _cover_square_enough(self, x: int, y: int) -> bool:
        aspect = 0 if max(x, y) == 0 else min(x, y) / max(x, y)
        return aspect >= self.cover_squareness

    def _image_table(
        self, album: Album, pictures: list[Picture], picture_sources: dict[Picture, list[tuple[str, bool]]]
    ) -> Sequence[Sequence[RenderableType]]:
        pixelses: list[Pixels] = []
        target_width = int((self.ctx.console.width - 3) / len(pictures))
        target_height = (self.ctx.console.height - 10) * 2
        for cover in pictures:
            (filename, embedded) = picture_sources[cover][0]
            path = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / filename
            if embedded:
                images = get_embedded_image_data(path)
                image_data = images[cover.embed_ix]
            else:
                with open(path, "rb") as f:
                    image_data = f.read()
            image = Image.open(io.BytesIO(image_data))
            h = (7 / 8) * image.height
            scale = min(target_width, target_height) / max(image.width, h)
            pixels = Pixels.from_image(image, (int(image.width * scale), int(h * scale)))
            pixelses.append(pixels)
        return [pixelses]

    def _describe_album_art(self, picture: Picture, picture_sources: dict[Picture, list[tuple[str, bool]]]):
        sources = picture_sources[picture]
        first_source = f"{escape(sources[0][0])}{f'#{picture.embed_ix}' if picture.embed_ix else ''}"
        details = f"[{picture.width} x {picture.height}] {humanize.naturalsize(picture.file_size, binary=True)}"
        return f"{first_source}{f' (and {len(sources) - 1} more)' if len(sources) > 1 else ''} {details}"

    def _select_cover(self, option: str, album: Album, front_covers: list[Picture], picture_sources: dict[Picture, list[tuple[str, bool]]]) -> bool:
        self.ctx.console.print(option)
        return False
