import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from ...database.models import AlbumEntity
from ...interactive.image_table import render_image_table
from ...picture.format import SUPPORTED_IMAGE_SUFFIXES
from ...tagger.types import Picture, PictureType
from ...types import CheckResult, Fixer
from ..base_check import Check
from ..helpers import delete_files_except

logger = logging.getLogger(__name__)


class CheckDuplicateImage(Check):
    name = "duplicate-image"
    default_config = {"enabled": True, "cover_only": False}
    must_pass_checks = {"invalid-image"}

    def init(self, check_config: dict[str, Any]):
        self.cover_only = bool(check_config.get("cover_only", CheckDuplicateImage.default_config["cover_only"]))

    def check(self, album: AlbumEntity) -> CheckResult | None:
        album_art = [(track.filename, True, [p.to_picture() for p in track.pictures]) for track in album.tracks]
        album_art.extend([(file.filename, False, [file.to_picture()]) for file in album.picture_files])

        pictures_by_type: defaultdict[PictureType, set[Picture]] = defaultdict(set)
        picture_sources: defaultdict[Picture, list[str]] = defaultdict(list)
        for filename, embedded, pictures in album_art:
            file_pics_by_content: defaultdict[Picture, list[Picture]] = defaultdict(list)
            for picture in pictures:
                if picture.type != PictureType.COVER_FRONT and self.cover_only:
                    continue
                picture_sources[picture].append(filename)
                pictures_by_type[picture.type].add(picture)
                if embedded:
                    file_pics_by_content[picture].append(picture)

            # if we have duplicate or conflicting embedded images within one track, stop and fix - might have to do this for each track
            for unique_picture in file_pics_by_content:
                if len(file_pics_by_content[unique_picture]) > 1:
                    # TODO: configurably allow duplicate image data if the picture_type is not the same
                    pic_types = ", ".join(sorted(set(pic.type.name for pic in file_pics_by_content[unique_picture])))
                    return CheckResult(f"duplicate embedded image data in one or more files: {pic_types}")

        # TODO dedup for all pictures, if not self.cover_only
        front_covers = pictures_by_type.get(PictureType.COVER_FRONT, [])
        cover_image_file = list(
            pic for pic in front_covers if any(Path(filename).suffix in SUPPORTED_IMAGE_SUFFIXES for filename in picture_sources[pic])
        )
        for pic in cover_image_file:
            filenames = sorted(filename for filename in picture_sources[pic] if Path(filename).suffix in SUPPORTED_IMAGE_SUFFIXES)
            if len(filenames) > 1:
                table = (filenames, lambda: render_image_table(self.ctx, self.tagger.get(album.path), [pic] * len(filenames), picture_sources))
                option_automatic_index = filenames.index(min(filenames, key=lambda s: len(s)))  # pick shortest filename
                return CheckResult(
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
