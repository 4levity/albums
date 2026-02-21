import io
import logging
from os import unlink
from pathlib import Path
from typing import Any, Callable, Tuple

from PIL.Image import Image

from albums.database.operations import update_picture_files
from albums.interactive.image_table import render_image_table
from albums.library.metadata import read_image

from ...types import Album, CheckResult, Fixer, Picture, PictureType, ProblemCategory
from ..base_check import Check

logger = logging.getLogger(__name__)


class CheckCoverDimensions(Check):
    name = "cover-dimensions"
    default_config = {
        "enabled": True,
        "min_pixels": 100,
        "max_pixels": 4096,
        "squareness": 0.98,
        "fixable_squareness": 0.8,
        "max_crop": 0.03,
    }
    must_pass_checks = {"cover-available"}  # either all the COVER_FRONT images are the same or there is a cover_source selected

    def init(self, check_config: dict[str, Any]):
        self.min_pixels = int(check_config.get("min_pixels", CheckCoverDimensions.default_config["min_pixels"]))
        self.max_pixels = int(check_config.get("max_pixels", CheckCoverDimensions.default_config["max_pixels"]))
        self.squareness = float(check_config.get("squareness", CheckCoverDimensions.default_config["squareness"]))
        if self.squareness > 1:
            raise ValueError("cover-dimensions.squareness must be between 0 and 1")
        self.fixable_squareness = float(check_config.get("fixable_squareness", CheckCoverDimensions.default_config["fixable_squareness"]))
        if self.fixable_squareness > 1:
            raise ValueError("cover-dimensions.fixable_squareness must be between 0 and 1")
        self.max_crop = float(check_config.get("max_crop", CheckCoverDimensions.default_config["max_crop"]))
        if self.max_crop > 1:
            raise ValueError("cover-dimensions.max_crop must be between 0 and 1")

    def check(self, album: Album) -> CheckResult | None:
        issues: set[str] = set()
        embedded_covers: dict[Picture, str] = {}
        for track in album.tracks:
            covers = [pic for pic in track.pictures if pic.picture_type == PictureType.COVER_FRONT]
            if covers:
                embedded_covers[covers[0]] = track.filename
        cover_files = [(pic, filename) for filename, pic in album.picture_files.items() if pic.picture_type == PictureType.COVER_FRONT]

        if len(cover_files) > 1:
            return CheckResult(ProblemCategory.PICTURES, "there is more than one front cover image file (check cover-unique suggested)")
        file_cover = cover_files[0][0] if cover_files else None
        if len(embedded_covers) > 1:
            return CheckResult(ProblemCategory.PICTURES, "more than one unique embedded cover image file (check cover-unique suggested)")
        embedded_cover = list(embedded_covers.items())[0][0] if embedded_covers else None
        if file_cover and embedded_cover and not file_cover.cover_source and file_cover != embedded_cover:
            return CheckResult(ProblemCategory.PICTURES, "cover image file not unique, not cover_source (check cover-unique suggested)")

        if file_cover:  # either cover_source or identical to embedded images
            (cover, from_file) = cover_files[0]
            embedded = False
        elif embedded_cover:
            (cover, from_file) = list(embedded_covers.items())[0]
            embedded = True
        else:
            return None  # no cover means cover-available is not configured to require one

        if min(cover.height, cover.width) < self.min_pixels:
            # we think we have selected the best cover image, no automated fix here
            issues.add(f"COVER_FRONT image is too small ({cover.width}x{cover.height})")
        if max(cover.height, cover.width) > self.max_pixels:
            # TODO: extract original to file, then resize/compress
            issues.add(f"COVER_FRONT image is too large ({cover.width}x{cover.height})")
        if not self._cover_square_enough(cover.width, cover.height):
            message = f"COVER_FRONT is not square ({cover.width}x{cover.height})"
            if not issues and self._can_squarify(cover.width, cover.height):  # squarify if image is not too small/large/unsquare
                options = [">> Make cover image square"]
                option_automatic_index = 0
                picture_source = {cover: [(from_file, embedded, cover.embed_ix)]}
                source_file = from_file if not embedded else None
                new_cover: list[Tuple[Picture, Image, bytes]] = []

                def get_new_cover():
                    if not new_cover:
                        (filename, embedded, _) = picture_source[cover][0]
                        (image, image_data) = self._squarify(cover, embedded, self.ctx.config.library / album.path / filename)
                        new_cover.append(
                            (Picture(cover.picture_type, "image/png", image.width, image.height, len(image_data), b""), image, image_data)
                        )
                    return new_cover[0]

                table = (
                    [f"Front cover {from_file}{f'#{cover.embed_ix}' if embedded else ''}", "Preview"],
                    lambda: self._render_table(album, cover, picture_source, get_new_cover),
                )
                return CheckResult(
                    ProblemCategory.PICTURES,
                    message,
                    Fixer(
                        lambda _: self._fix_save_new_cover(album, source_file, get_new_cover()[2]),
                        options,
                        False,
                        option_automatic_index,
                        table,
                    ),
                )
            else:
                issues.add(message)

        if issues:
            return CheckResult(ProblemCategory.PICTURES, ", ".join(list(issues)))

    def _fix_save_new_cover(self, album: Album, source_filename: str | None, image_data: bytes):
        if not self.ctx.db or album.album_id is None:
            raise RuntimeError("saving new cover requires db + album_id")

        if source_filename:
            original_path = self.ctx.config.library / album.path / source_filename
            if original_path.suffix == ".png":
                new_path = original_path
                original_path = None  # overwrite
            else:
                new_path = original_path.with_suffix(".png")
        else:
            original_path = None
            new_path = self.ctx.config.library / album.path / "cover.png"
        if original_path and source_filename:
            self.ctx.console.print(f"Deleting {source_filename}")
            unlink(original_path)
            del album.picture_files[source_filename]

        # mark new/replaced image as cover_source (metadata will be picked up in rescan)
        album.picture_files[new_path.name] = Picture(PictureType.COVER_FRONT, "image/png", 0, 0, 0, b"", "", None, 0, cover_source=True)
        update_picture_files(self.ctx.db, album.album_id, album.picture_files)

        with open(new_path, "wb") as f:
            self.ctx.console.print(f"Writing {new_path.name}")
            f.write(image_data)
        return True

    def _render_table(
        self,
        album: Album,
        cover: Picture,
        picture_source: dict[Picture, list[tuple[str, bool, int]]],
        get_preview: Callable[[], Tuple[Picture, Image, bytes]],
    ):
        preview = get_preview()
        return render_image_table(self.ctx, album, [cover, preview], picture_source)

    def _cover_square_enough(self, w: int, h: int) -> bool:
        return self._aspect(w, h) >= self.squareness

    def _aspect(self, w: int, h: int):
        return 0 if max(w, h) == 0 else min(w, h) / max(w, h)

    def _can_squarify(self, w: int, h: int):
        return not self._cover_square_enough(w, h) and self._aspect(w, h) >= self.fixable_squareness

    def _squarify(self, pic: Picture, embedded: bool, path: Path):
        loaded_image = read_image(path, embedded, pic.embed_ix)
        if not loaded_image:
            raise RuntimeError(f"failed to read image {str(path)}{f'#{pic.embed_ix}' if embedded else ''}")
        (image, _) = loaded_image
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        if image.width < image.height:
            target_width = image.width
            target_height = image.width
        elif image.width > image.height:
            target_width = image.height
            target_height = image.height
        else:
            raise ValueError("image was already square")

        width_reduction = min(image.width - target_width, image.width * self.max_crop)
        height_reduction = min(image.height - target_height, image.height * self.max_crop)
        left = int(width_reduction / 2)
        upper = int(height_reduction / 2)
        right = left + image.width - width_reduction
        lower = upper + image.height - height_reduction
        image = image.crop((left, upper, right, lower))

        # if cropped image is still not square, squash it the rest of the way
        if image.width < image.height:
            image = image.resize((image.width, image.width))
        elif image.width > image.height:
            image = image.resize((image.height, image.height))
        buffer = io.BytesIO()
        image.save(buffer, "PNG")  # TODO option to preserve original type or use JPG
        return (image, buffer.getvalue())
