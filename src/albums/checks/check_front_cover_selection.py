import logging
from collections import defaultdict
from typing import Any, Collection, Sequence

from rich.markup import escape

from ..database import operations
from ..types import Album, Picture, PictureType
from .base_check import Check, CheckResult, Fixer, ProblemCategory
from .helpers import delete_files_except
from .image_table import render_image_table

logger = logging.getLogger(__name__)

OPTION_DELETE_ALL_COVER_IMAGES = ">> Delete all cover image files: "
OPTION_SELECT_COVER_IMAGE = ">> Mark as front cover source: "


class CheckFrontCoverSelection(Check):
    name = "front_cover_selection"
    default_config = {"enabled": True, "cover_required": False, "unique": True}
    must_pass_checks = {"duplicate_images"}

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
        for filename, embedded, pictures in album_art:
            file_cover: Picture | None = None
            for picture in pictures:
                picture_sources[picture].append((filename, embedded))
                pictures_by_type[picture.picture_type].add(picture)
                if picture.picture_type == PictureType.COVER_FRONT:
                    if file_cover is None:
                        file_cover = picture
            if embedded:
                if file_cover:
                    tracks_with_cover += 1

        front_covers: set[Picture] = pictures_by_type.get(PictureType.COVER_FRONT, set())
        front_cover_image_file = list(
            pic
            for pic in sorted(front_covers, key=lambda pic: pic.file_size, reverse=True)
            if any(not embedded for (_, embedded) in picture_sources[pic])
        )

        if self.unique and len(front_covers) > 1:
            front_cover_embedded = list(pic for pic in front_covers if any(embedded for (_, embedded) in picture_sources[pic]))
            has_cover_source_file = any(cover.front_cover_source for cover in front_covers)
            if front_cover_image_file and not has_cover_source_file:
                # at this point every picture in front_cover_image_file should be associated with exactly one file
                cover_image_filenames = [[file for (file, embedded) in picture_sources[pic] if not embedded][0] for pic in front_cover_image_file]
                cover_source_candidate = self._source_image_file_candidate(front_cover_image_file, front_cover_embedded)
                cover_embedded_desc = [self._describe_album_art(pic, picture_sources) for pic in front_cover_embedded]
                options = [f"{OPTION_SELECT_COVER_IMAGE}{filename}" for filename in cover_image_filenames]
                if front_cover_embedded:
                    options.append(f"{OPTION_DELETE_ALL_COVER_IMAGES}{', '.join(escape(filename) for filename in cover_image_filenames)}")
                table = (
                    cover_image_filenames + cover_embedded_desc,
                    lambda: render_image_table(self.ctx, album, front_cover_image_file + front_cover_embedded, picture_sources),
                )
                if cover_source_candidate:
                    # if there is a higher-resolution cover file, this conflict can be solved or reduced by marking that file as cover source
                    option_automatic_index = front_cover_image_file.index(cover_source_candidate)
                    message = "multiple cover art images: designate a high-resolution image file as cover art source"
                    if front_cover_embedded:
                        message += " or delete image files (keep embedded images)"
                    else:
                        message += " (tracks do not have embedded images)"
                else:
                    # if none of the cover image files are larger than embedded covers, we can delete them or mark one as cover front source
                    option_automatic_index = None
                    message = "there are cover image files with the album, but none bigger than embedded cover images"
                return CheckResult(
                    ProblemCategory.PICTURES,
                    message,
                    Fixer(
                        lambda option: self._fix_select_cover_source_or_delete(album, option, options, cover_image_filenames),
                        options,
                        False,
                        option_automatic_index,
                        table,
                    ),
                )
            elif has_cover_source_file and len(front_cover_image_file) > 1:
                # TODO if there is a cover source and there are multiple cover image files, offer to keep only the cover source
                issues.add("multiple front cover image files, but one of them is marked cover source (delete others)")
            elif not has_cover_source_file or len(front_cover_image_file) > 1 or len(front_cover_embedded) > 1:
                # TODO if multiple front cover embedded + each track has one, that's probably on purpose and maybe should be ignored?
                issues.add("COVER_FRONT pictures are not all the same")

        if not front_covers:
            if pictures_by_type:
                issues.add("album has pictures but none is COVER_FRONT picture")
            elif self.cover_required:
                issues.add("album does not have a COVER_FRONT picture")

        # TODO move to later front-cover-embedding check
        if front_covers and tracks_with_cover and tracks_with_cover != len(album.tracks):
            issues.add("some tracks have COVER_FRONT and some do not")

        if issues:
            return CheckResult(ProblemCategory.PICTURES, ", ".join(list(issues)))

    def _describe_album_art(self, picture: Picture, picture_sources: dict[Picture, list[tuple[str, bool]]]):
        sources = picture_sources[picture]
        first_source = f"{escape(sources[0][0])}{f'#{picture.embed_ix}' if picture.embed_ix else ''}"
        details = f"{picture.format}"
        return f"{first_source}{f' (and {len(sources) - 1} more)' if len(sources) > 1 else ''} {details}"

    def _source_image_file_candidate(self, image_files: Collection[Picture], embedded_images: Collection[Picture]):
        largest_image_file = max(image_files, key=lambda pic: pic.file_size) if image_files else None
        largest_embedded_file = max(embedded_images, key=lambda pic: pic.file_size) if embedded_images else None
        if largest_embedded_file is None or (largest_image_file and largest_image_file.file_size > largest_embedded_file.file_size):
            return largest_image_file
        return None

    def _fix_select_cover_source_or_delete(self, album: Album, option: str, options: Sequence[str], all_filenames: Sequence[str]) -> bool:
        if option.startswith(OPTION_DELETE_ALL_COVER_IMAGES):
            return delete_files_except(self.ctx, None, album, all_filenames)
        elif option.startswith(OPTION_SELECT_COVER_IMAGE) and self.ctx.db and album.album_id:
            filename = all_filenames[options.index(option)]
            for picfile in album.picture_files:
                album.picture_files[picfile].front_cover_source = picfile == filename
            self.ctx.console.print(f"setting cover source file to {escape(filename)}")
            operations.update_picture_files(self.ctx.db, album.album_id, album.picture_files)
            return True
        raise ValueError(f"invalid option {option}")
