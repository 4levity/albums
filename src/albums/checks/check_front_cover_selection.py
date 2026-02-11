import io
import logging
from collections import defaultdict
from os import unlink
from pathlib import Path
from typing import Any, Collection, List, Sequence

import humanize
import numpy
from PIL import Image, UnidentifiedImageError
from rich.console import RenderableType
from rich.markup import escape
from rich_pixels import Pixels
from skimage.metrics import mean_squared_error  # pyright: ignore[reportUnknownVariableType]

from ..database import operations
from ..library.metadata import get_embedded_image_data
from ..types import Album, Picture, PictureType
from .base_check import Check, CheckResult, Fixer, ProblemCategory

logger = logging.getLogger(__name__)

OPTION_DELETE_ALL_COVER_IMAGES = ">> Delete all cover image files: "
OPTION_SELECT_COVER_IMAGE = ">> Mark as front cover source: "


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

        front_covers = pictures_by_type.get(PictureType.COVER_FRONT, [])
        front_cover_image_file = list(pic for pic in front_covers if any(not embedded for (_, embedded) in picture_sources[pic]))
        for pic in front_cover_image_file:
            sources = sorted(filename for (filename, embedded) in picture_sources[pic] if not embedded)
            if len(sources) > 1:
                table = (sources, lambda: self._image_table(album, [pic] * len(sources), picture_sources))
                option_automatic_index = sources.index(min(sources, key=lambda s: len(s)))  # pick shortest filename
                return CheckResult(
                    ProblemCategory.PICTURES,
                    f"same image data in multiple files: {', '.join(sources)}",
                    Fixer(
                        lambda option: self._fix_delete_image_files_except(option, sources, album),
                        sources,
                        False,
                        option_automatic_index,
                        table,
                        "Select one file to KEEP and all the other files will be DELETED",
                    ),
                )

        if self.unique and len(front_covers) > 1:
            front_cover_embedded = list(pic for pic in front_covers if any(embedded for (_, embedded) in picture_sources[pic]))
            has_cover_source_file = any(cover.front_cover_source for cover in front_covers)
            message = None

            if front_cover_image_file and not has_cover_source_file:
                # at this point every picture in front_cover_image_file should be associated with exactly one file
                cover_image_filename = [[file for (file, embedded) in picture_sources[pic] if not embedded][0] for pic in front_cover_image_file]
                cover_source_candidate = self._source_image_file_candidate(front_cover_image_file, front_cover_embedded)
                if cover_source_candidate:
                    # if there is a higher-resolution cover file, this conflict can be solved or reduced by marking that file as cover source
                    option_automatic_index = front_cover_image_file.index(cover_source_candidate)
                    table = (cover_image_filename, lambda: self._image_table(album, front_cover_image_file, picture_sources))
                    return CheckResult(
                        ProblemCategory.PICTURES,
                        f"an image file should be set as front cover source if it is being kept: {', '.join(cover_image_filename)}",
                        Fixer(
                            lambda filename: self._fix_select_cover_source_file(album, filename),
                            cover_image_filename,
                            False,
                            option_automatic_index,
                            table,
                            "Select an image file to mark as album cover source",
                        ),
                    )
                else:
                    # if none of the cover image files are larger than embedded covers, offer to delete them or mark one as cover front source
                    options = [f"{OPTION_SELECT_COVER_IMAGE}{filename}" for filename in cover_image_filename] + [
                        f"{OPTION_DELETE_ALL_COVER_IMAGES}{', '.join(escape(filename) for filename in cover_image_filename)}"
                    ]
                    cover_embedded_desc = [self._describe_album_art(pic, picture_sources) for pic in front_cover_embedded]
                    table = (
                        cover_image_filename + cover_embedded_desc,
                        lambda: self._image_table(album, front_cover_image_file + front_cover_embedded, picture_sources),
                    )
                    option_automatic_index = None
                    return CheckResult(
                        ProblemCategory.PICTURES,
                        "there are cover image files with the album, but none bigger than embedded cover images",
                        Fixer(
                            lambda option: self._fix_select_cover_source_or_delete(album, option, options, cover_image_filename),
                            options,
                            False,
                            option_automatic_index,
                            table,
                        ),
                    )

            elif duplicate_in_track:
                message = "COVER_FRONT picture cleanup needed"
            elif not has_cover_source_file or len(front_cover_image_file) > 1 or len(front_cover_embedded) > 1:
                # TODO if multiple front cover embedded + each track has one, that's probably on purpose and maybe should be ignored?
                # if there is a cover source and there are multiple cover image files, offer to keep only the cover source
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
            # if tracks_with_cover:
            # candidates: set[Picture] = front_covers if front_covers else set().union(*pictures_by_type.values())  # type: ignore
            # picture_list = sorted(candidates, key=lambda picture: len(picture_sources[picture]), reverse=True)
            # options = [self._describe_album_art(picture, picture_sources) for picture in picture_list]

            # TODO options (a) if there are front cover picture files, mark one of them as cover front source
            # TODO options (b) select one of the images and embed it in all the files (b-plus) after resizing it to 500x500 if larger source is available and compressing it
            # fixer = Fixer(
            #     lambda option: self._select_cover(option, album, picture_list, picture_sources),
            #     options,
            #     False,
            #     None,
            #     (options, lambda: self._image_table(album, picture_list, picture_sources)),
            # )
            # else:
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
        captions: list[RenderableType] = []
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
                h = (7 / 8) * image.height  # TODO try to determine appropriate height scaling for terminal font or make configurable
                scale = min(target_width, target_height) / max(image.width, h)
                pixels = Pixels.from_image(image, (int(image.width * scale), int(h * scale)))
                pixelses.append(pixels)
                caption = f"[{cover.width} x {cover.height}] {humanize.naturalsize(len(image_data), binary=True)}"
                if len(pictures) > 1:
                    COMPARISON_BOX_SIZE = 75
                    image.thumbnail((COMPARISON_BOX_SIZE, COMPARISON_BOX_SIZE), Image.Resampling.BOX)
                    image = image.convert("RGB")
                    if reference_image is not None:
                        if image.width != reference_width or image.height != reference_height:
                            caption += " aspect ratio doesn't match"
                        else:
                            this_image = numpy.asarray(image)
                            mse = mean_squared_error(reference_image, this_image)
                            caption += f" mean-squared-error difference={mse:.2f}"
                    else:
                        reference_image = numpy.asarray(image)
                        (reference_width, reference_height) = image.size
                        caption += " reference"
                captions.append(caption)
        return [pixelses, captions] if captions else [pixelses]

    def _describe_album_art(self, picture: Picture, picture_sources: dict[Picture, list[tuple[str, bool]]]):
        sources = picture_sources[picture]
        first_source = f"{escape(sources[0][0])}{f'#{picture.embed_ix}' if picture.embed_ix else ''}"
        details = f"{picture.format}"
        return f"{first_source}{f' (and {len(sources) - 1} more)' if len(sources) > 1 else ''} {details}"

    def _fix_select_cover_source_file(self, album: Album, filename: str) -> bool:
        if self.ctx.db and album.album_id:
            for picfile in album.picture_files:
                album.picture_files[picfile].front_cover_source = picfile == filename
            self.ctx.console.print(f"setting cover source file to {escape(filename)}")
            operations.update_picture_files(self.ctx.db, album.album_id, album.picture_files)
        return True

    def _source_image_file_candidate(self, image_files: Collection[Picture], embedded_images: Collection[Picture]):
        largest_image_file = max(image_files, key=lambda pic: pic.file_size) if image_files else None
        largest_embedded_file = max(embedded_images, key=lambda pic: pic.file_size) if embedded_images else None
        if largest_embedded_file is None or (largest_image_file and largest_image_file.file_size > largest_embedded_file.file_size):
            return largest_image_file
        return None

    def _fix_delete_image_files_except(self, option: str | None, filenames: Collection[str], album: Album):
        if option is not None and option not in filenames:
            raise ValueError(f"invalid option {option} is not one of {filenames}")

        for filename in filenames:
            if filename == option:
                self.ctx.console.print(f"Keeping {escape(filename)}")
            else:
                self.ctx.console.print(f"Deleting {escape(filename)}")
                path = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / filename
                unlink(path)
        return True

    def _fix_select_cover_source_or_delete(self, album: Album, option: str, options: Sequence[str], all_filenames: Sequence[str]) -> bool:
        if option.startswith(OPTION_DELETE_ALL_COVER_IMAGES):
            return self._fix_delete_image_files_except(None, all_filenames, album)
        elif option.startswith(OPTION_SELECT_COVER_IMAGE):
            filename = all_filenames[options.index(option)]
            return self._fix_select_cover_source_file(album, filename)
        raise ValueError(f"invalid option {option}")
