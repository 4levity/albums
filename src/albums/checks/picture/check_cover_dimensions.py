import io
import logging
import mimetypes
from itertools import chain
from os import unlink
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from PIL import Image

from ...database.operations import update_picture_files
from ...interactive.image_table import render_image_table
from ...picture.format import IMAGE_MODE_BPP, MIME_PILLOW_FORMAT
from ...picture.info import PictureInfo
from ...tagger.types import Picture, PictureType
from ...types import Album, CheckResult, Fixer, PictureFile
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
        "create_mime_type": "image/png",
        "create_jpeg_quality": 80,
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
        self.create_mime_type = str(check_config.get("create_mime_type", CheckCoverDimensions.default_config["create_mime_type"]))
        if self.create_mime_type != "" and self.create_mime_type not in MIME_PILLOW_FORMAT:
            raise ValueError(f"cover-dimensions.create_mime_type must be blank or one of {', '.join(MIME_PILLOW_FORMAT.keys())}")
        self.create_jpeg_quality = int(check_config.get("create_jpeg_quality", CheckCoverDimensions.default_config["create_jpeg_quality"]))
        if self.create_jpeg_quality < 1 or self.create_jpeg_quality > 95:
            raise ValueError("cover-dimensions.create_jpeg_quality must be between 1 and 95")

    def check(self, album: Album) -> CheckResult | None:
        issues: set[str] = set()
        embedded_covers: dict[Picture, str] = {}
        for track in album.tracks:
            covers = [pic for pic in track.pictures if pic.type == PictureType.COVER_FRONT]
            if covers:
                embedded_covers[covers[0]] = track.filename
        cover_files = [file for file in album.picture_files if PictureType.from_filename(file.filename) == PictureType.COVER_FRONT]
        if all(
            self._cover_good_enough(cover)
            for cover in chain(embedded_covers.keys(), (Picture(file.file_info, PictureType.COVER_FRONT, "") for file in cover_files))
        ):
            return None

        if len(cover_files) > 1:
            return CheckResult(
                "some cover dimensions are out of range, and there is more than one front cover image file (check cover-unique suggested)"
            )
        file_cover = cover_files[0] if cover_files else None
        if len(embedded_covers) > 1:
            return CheckResult(
                "some cover dimensions are out of range, and there is more than one unique embedded cover image file (check cover-unique suggested)"
            )

        if embedded_covers:
            (embedded_cover, _filename) = list(embedded_covers.items())[0]
        else:
            embedded_cover = None

        if file_cover and embedded_cover and not file_cover.cover_source and file_cover.file_info.file_hash != embedded_cover.file_info.file_hash:
            return CheckResult(
                "some cover dimensions are out of range, cover image file is not unique and not cover_source (check cover-unique suggested)"
            )

        if file_cover:  # either cover_source or identical to embedded images
            cover_file = cover_files[0]
            from_file = cover_file.filename
            cover = Picture(cover_file.file_info, PictureType.COVER_FRONT, "")
            embedded = False
        elif embedded_cover:
            (cover, from_file) = list(embedded_covers.items())[0]
            embedded = True
        else:
            return None  # no cover means cover-available is not configured to require one

        if min(cover.file_info.height, cover.file_info.width) < self.min_pixels:
            # we think we have selected the best cover image, no automated fix here
            issues.add(f"COVER_FRONT image is too small ({cover.file_info.width}x{cover.file_info.height})")
        if max(cover.file_info.height, cover.file_info.width) > self.max_pixels:
            # TODO: extract original to file, then resize/compress
            issues.add(f"COVER_FRONT image is too large ({cover.file_info.width}x{cover.file_info.height})")
        if not self._cover_square_enough(cover.file_info.width, cover.file_info.height):
            message = f"COVER_FRONT is not square ({cover.file_info.width}x{cover.file_info.height})"
            if not issues and self._can_squarify(cover.file_info.width, cover.file_info.height):  # squarify if image is not too small/large/unsquare
                options = [">> Make cover image square"]
                option_automatic_index = 0
                picture_source: Dict[Picture, List[str]] = {cover: [from_file]}
                source_file = from_file if not embedded else None
                new_cover: list[Tuple[Picture, Image.Image, bytes]] = []

                def make_new_cover():
                    if not new_cover:
                        filename = picture_source[cover][0]
                        (image, image_data, mime_type) = self._squarify(cover, self.ctx.config.library / album.path, filename)
                        pic_info = PictureInfo(mime_type, image.width, image.height, IMAGE_MODE_BPP.get(image.mode, 0), len(image_data), b"")
                        new_cover.append((Picture(pic_info, cover.type, ""), image, image_data))
                    return new_cover[0]

                table = (
                    [f"Front cover {from_file}", "Preview"],
                    lambda: self._render_table(album, cover, picture_source, make_new_cover),
                )
                return CheckResult(
                    message,
                    Fixer(
                        lambda _: self._fix_save_new_cover(album, source_file, make_new_cover),
                        options,
                        False,
                        option_automatic_index,
                        table,
                    ),
                )
            else:
                issues.add(message)

        if issues:
            return CheckResult(", ".join(list(issues)))

    def _fix_save_new_cover(self, album: Album, source_filename: str | None, get_image_data: Callable[[], Tuple[Picture, Image.Image, bytes]]):
        if not self.ctx.db or album.album_id is None:
            raise RuntimeError("saving new cover requires db + album_id")
        (picture, _, image_data) = get_image_data()
        suffix = mimetypes.guess_extension(picture.file_info.mime_type)
        if not suffix:
            raise ValueError(f"couldn't generate image type {picture.file_info.mime_type} - can't guess file extension")
        if source_filename:
            original_path = self.ctx.config.library / album.path / source_filename
            if original_path.suffix == suffix:
                new_path = original_path
                original_path = None  # overwrite
            else:
                new_path = original_path.with_suffix(suffix)
        else:
            original_path = None
            new_path = self.ctx.config.library / album.path / f"cover{suffix}"

        if original_path and source_filename:
            self.ctx.console.print(f"Deleting {source_filename}")
            unlink(original_path)
            picture_files = [file for file in album.picture_files if file.filename != source_filename]
        else:
            picture_files = list(album.picture_files)

        # mark new/replaced image as cover_source
        picture_files.append(PictureFile(new_path.name, picture.file_info, 0, cover_source=True))
        album.picture_files = picture_files
        update_picture_files(self.ctx.db, album.album_id, album.picture_files)

        with open(new_path, "wb") as f:
            self.ctx.console.print(f"Writing {new_path.name}")
            f.write(image_data)
        return True

    def _render_table(
        self,
        album: Album,
        cover: Picture,
        picture_source: Dict[Picture, List[str]],
        get_preview: Callable[[], Tuple[Picture, Image.Image, bytes]],
    ):
        preview = get_preview()
        return render_image_table(self.ctx, self.tagger.get(album.path), [cover, preview], picture_source)

    def _cover_good_enough(self, cover: Picture):
        return (
            min(cover.file_info.height, cover.file_info.width) >= self.min_pixels
            and max(cover.file_info.height, cover.file_info.width) <= self.max_pixels
            and self._cover_square_enough(cover.file_info.width, cover.file_info.height)
        )

    def _cover_square_enough(self, w: int, h: int) -> bool:
        return self._aspect(w, h) >= self.squareness

    def _aspect(self, w: int, h: int):
        return 0 if max(w, h) == 0 else min(w, h) / max(w, h)

    def _can_squarify(self, w: int, h: int):
        return not self._cover_square_enough(w, h) and self._aspect(w, h) >= self.fixable_squareness

    def _squarify(self, pic: Picture, path: Path, filename: str):
        with self.tagger.get(path).open(filename) as tags:
            image_data = tags.get_image_data(pic)

        image = Image.open(io.BytesIO(image_data))
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

        if self.create_mime_type == "" and image.format:
            mime_type, _ = mimetypes.guess_type(f"_.{image.format}")
        else:
            mime_type = self.create_mime_type
        if not mime_type:
            mime_type = "image/png"

        width_reduction = min(image.width - target_width, image.width * self.max_crop)
        height_reduction = min(image.height - target_height, image.height * self.max_crop)
        left = int(width_reduction / 2)
        upper = int(height_reduction / 2)
        right = left + image.width - width_reduction
        lower = upper + image.height - height_reduction
        image = image.crop((left, upper, right, lower))

        # if cropped image is still not square, squash it the rest of the way
        if image.width < image.height:
            image = image.resize((image.width, image.width), resample=Image.Resampling.LANCZOS)
        elif image.width > image.height:
            image = image.resize((image.height, image.height), resample=Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        format = MIME_PILLOW_FORMAT[mime_type]
        image.save(buffer, format, quality=self.create_jpeg_quality)
        return (image, buffer.getvalue(), mime_type)
