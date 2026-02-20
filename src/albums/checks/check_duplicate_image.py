import logging
from collections import defaultdict
from typing import Any

from rich.markup import escape

from ..interactive.image_table import render_image_table
from ..types import Album, CheckResult, Fixer, Picture, PictureType, ProblemCategory
from .base_check import Check
from .helpers import delete_files_except

logger = logging.getLogger(__name__)

OPTION_DELETE_ALL_COVER_IMAGES = ">> Delete all cover image files: "
OPTION_SELECT_COVER_IMAGE = ">> Mark as front cover source: "


class CheckDuplicateImage(Check):
    name = "duplicate_image"
    default_config = {"enabled": True, "cover_only": False}
    must_pass_checks = {"invalid_image"}

    def init(self, check_config: dict[str, Any]):
        self.cover_only = bool(check_config.get("cover_only", CheckDuplicateImage.default_config["cover_only"]))

    def check(self, album: Album) -> CheckResult | None:
        album_art = [(track.filename, True, track.pictures) for track in album.tracks]
        album_art.extend([(filename, False, [picture]) for filename, picture in album.picture_files.items()])

        pictures_by_type: defaultdict[PictureType, set[Picture]] = defaultdict(set)
        picture_sources: defaultdict[Picture, list[tuple[str, bool, int]]] = defaultdict(list)
        for filename, embedded, pictures in album_art:
            file_pics_by_type: defaultdict[PictureType, list[Picture]] = defaultdict(list)
            file_pics_by_content: defaultdict[Picture, list[Picture]] = defaultdict(list)
            for picture in pictures:
                if picture.picture_type != PictureType.COVER_FRONT and self.cover_only:
                    continue
                picture_sources[picture].append((filename, embedded, picture.embed_ix))
                pictures_by_type[picture.picture_type].add(picture)
                if embedded:
                    file_pics_by_type[picture.picture_type].append(picture)
                    file_pics_by_content[picture].append(picture)

            # if we have duplicate or conflicting embedded images within one track, stop and fix - might have to do this for each track
            for unique_picture in file_pics_by_content:
                if len(file_pics_by_content[unique_picture]) > 1:
                    # TODO: configurably allow duplicate image data if the picture_type is not the same
                    pic_types = ", ".join(sorted(set(pic.picture_type.name for pic in file_pics_by_content[unique_picture])))
                    return CheckResult(ProblemCategory.PICTURES, f"duplicate embedded image data in one or more files: {pic_types}")
            for picture_type in file_pics_by_type:
                if len(file_pics_by_type[picture_type]) > 1:
                    message = f"there are {len(file_pics_by_type[picture_type])} different images for {picture_type.name} in one or more files"
                    return CheckResult(ProblemCategory.PICTURES, message)

        # TODO dedup for all pictures, if not self.cover_only
        front_covers = pictures_by_type.get(PictureType.COVER_FRONT, [])
        cover_image_file = list(pic for pic in front_covers if any(not embedded for (_, embedded, _ix) in picture_sources[pic]))
        for pic in cover_image_file:
            filenames = sorted(filename for (filename, embedded, _ix) in picture_sources[pic] if not embedded)
            if len(filenames) > 1:
                table = (filenames, lambda: render_image_table(self.ctx, album, [pic] * len(filenames), picture_sources))
                option_automatic_index = filenames.index(min(filenames, key=lambda s: len(s)))  # pick shortest filename
                return CheckResult(
                    ProblemCategory.PICTURES,
                    f"same image data in multiple files: {', '.join(filenames)}",
                    Fixer(
                        lambda option: delete_files_except(self.ctx, option, album, filenames),
                        filenames,
                        False,
                        option_automatic_index,
                        table,
                        "Select one file to KEEP and all the other files will be DELETED",
                    ),
                )

    def _describe_album_art(self, picture: Picture, picture_sources: dict[Picture, list[tuple[str, bool]]]):
        sources = picture_sources[picture]
        first_source = f"{escape(sources[0][0])}{f'#{picture.embed_ix}' if picture.embed_ix else ''}"
        details = f"{picture.format}"
        return f"{first_source}{f' (and {len(sources) - 1} more)' if len(sources) > 1 else ''} {details}"
