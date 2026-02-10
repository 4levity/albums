import io
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, List

import humanize
import numpy
from PIL import Image, UnidentifiedImageError
from rich.console import RenderableType
from rich.markup import escape
from rich_pixels import Pixels
from skimage.metrics import mean_squared_error  # pyright: ignore[reportUnknownVariableType]

from albums.library.metadata import get_embedded_image_data

from ..types import Album, Picture, PictureType
from .base_check import Check, CheckResult, Fixer, ProblemCategory

logger = logging.getLogger(__name__)


class CheckFrontCoverSelection(Check):
    name = "front_cover_selection"
    default_config = {"enabled": True, "cover_required": False, "unique": True}

    def init(self, check_config: dict[str, Any]):
        self.cover_required = bool(check_config.get("cover_required", CheckFrontCoverSelection.default_config["cover_required"]))
        self.unique = int(check_config.get("unique", CheckFrontCoverSelection.default_config["unique"]))

    def check(self, album: Album) -> CheckResult | None:
        if album.codec() not in {"FLAC", "MP3"} and self.cover_required:
            # if cover is required, only run check on albums where embedded pictures are supported
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
                if file_cover:
                    tracks_with_cover += 1

        front_covers = pictures_by_type.get(PictureType.COVER_FRONT)
        if front_covers and len(front_covers) > 1:
            front_cover_embedded = list(pic for pic in front_covers if any(embedded for (_, embedded) in picture_sources[pic]))
            front_cover_image_file = list(pic for pic in front_covers if any(not embedded for (_, embedded) in picture_sources[pic]))
            has_cover_source_file = any(cover.front_cover_source for cover in front_covers)
            if self.unique:
                message = None
                if front_cover_image_file and not has_cover_source_file:
                    # if there is a high resolution cover file, this conflict can be solved or reduced by marking that file as cover source
                    # but if none of the image files are larger or higher resolution than embedded files, offer to delete them instead
                    message = "select one of these files as cover source or delete them all"  # TODO fixer
                elif duplicate_in_track:
                    message = "COVER_FRONT picture cleanup needed"
                elif not has_cover_source_file or len(front_cover_image_file) > 1 or len(front_cover_embedded) > 1:
                    # if there is a cover source and there are multiple cover image files, offer to keep only the largest file
                    message = "COVER_FRONT pictures are not all the same"
                if message:
                    issues.add(message)

        if front_covers:
            if tracks_with_cover and tracks_with_cover != len(album.tracks):
                issues.add("some tracks have COVER_FRONT and some do not")
        elif pictures_by_type:
            issues.add("album has pictures but none is COVER_FRONT picture")
        elif self.cover_required:
            issues.add("album does not have a COVER_FRONT picture")

        if issues:
            if tracks_with_cover:
                candidates: set[Picture] = (  # pyright: ignore[reportUnknownVariableType]
                    front_covers if front_covers else set().union(*pictures_by_type.values())
                )
                picture_list = sorted(candidates, key=lambda picture: len(picture_sources[picture]), reverse=True)
                options = [self._describe_album_art(picture, picture_sources) for picture in picture_list]

                # TODO options (a) if there are front cover picture files, mark one of them as cover front source
                # TODO options (b) select one of the images and embed it in all the files (b-plus) after resizing it to 500x500 if larger source is available and compressing it
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
                ProblemCategory.PICTURES,
                ", ".join(list(issues)),
                fixer,
            )
            # return CheckResult(ProblemCategory.PICTURES, ", ".join(list(issues)))

    def _image_table(
        self, album: Album, pictures: list[Picture], picture_sources: dict[Picture, list[tuple[str, bool]]]
    ) -> List[List[RenderableType]]:
        pixelses: list[RenderableType] = []
        target_width = int((self.ctx.console.width - 3) / len(pictures))
        target_height = (self.ctx.console.height - 10) * 2
        differences: list[RenderableType] = []
        reference_image: numpy.ndarray[Any] | None = None
        reference_width = reference_height = 0
        for cover in pictures:
            (filename, embedded) = picture_sources[cover][0]
            path = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / filename
            if embedded:
                images = get_embedded_image_data(path)
                image_data = images[cover.embed_ix]
            else:
                with open(path, "rb") as f:
                    image_data = f.read()
            try:
                image = Image.open(io.BytesIO(image_data))
            except UnidentifiedImageError as ex:
                logger.error(f"failed to read image {str(path)}: {repr(ex)}")
                image = None

            if image:
                h = (7 / 8) * image.height
                scale = min(target_width, target_height) / max(image.width, h)
                pixels = Pixels.from_image(image, (int(image.width * scale), int(h * scale)))
                pixelses.append(pixels)
                if len(pictures) > 1:
                    COMPARISON_BOX_SIZE = 75
                    image.thumbnail((COMPARISON_BOX_SIZE, COMPARISON_BOX_SIZE), Image.Resampling.BOX)
                    image = image.convert("RGB")
                    if reference_image is not None:
                        if image.width != reference_width or image.height != reference_height:
                            differences.append("aspect ratio doesn't match")
                        else:
                            this_image = numpy.asarray(image)
                            mse = mean_squared_error(reference_image, this_image)
                            differences.append(f"MSE difference = {mse}")
                    else:
                        reference_image = numpy.asarray(image)
                        (reference_width, reference_height) = image.size
                        differences.append("reference")
        return [pixelses, differences] if differences else [pixelses]

    def _describe_album_art(self, picture: Picture, picture_sources: dict[Picture, list[tuple[str, bool]]]):
        sources = picture_sources[picture]
        first_source = f"{escape(sources[0][0])}{f'#{picture.embed_ix}' if picture.embed_ix else ''}"
        details = f"[{picture.width} x {picture.height}] {humanize.naturalsize(picture.file_size, binary=True)}"
        return f"{first_source}{f' (and {len(sources) - 1} more)' if len(sources) > 1 else ''} {details}"

    def _select_cover(self, option: str, album: Album, front_covers: list[Picture], picture_sources: dict[Picture, list[tuple[str, bool]]]) -> bool:
        # TODO implement selecting and applying cover, marking a file as front_cover_source, and deleting unwanted cover copies
        self.ctx.console.print(option)
        return False
