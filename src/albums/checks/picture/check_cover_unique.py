import logging
from collections import defaultdict
from typing import Collection, Sequence

from rich.markup import escape

from ...database import operations
from ...interactive.image_table import render_image_table
from ...types import Album, CheckResult, Fixer, Picture, PictureType, ProblemCategory
from ..base_check import Check
from ..helpers import delete_files_except

logger = logging.getLogger(__name__)

OPTION_DELETE_ALL_COVER_IMAGES = ">> Delete all cover image files: "
OPTION_SELECT_COVER_IMAGE = ">> Mark as front cover source: "


class CheckCoverUnique(Check):
    name = "cover-unique"
    default_config = {"enabled": True}
    must_pass_checks = {"duplicate-image"}

    def check(self, album: Album) -> CheckResult | None:
        tracks_with_cover = 0
        album_art = [(track.filename, True, track.pictures) for track in album.tracks]
        album_art.extend([(filename, False, [picture]) for filename, picture in album.picture_files.items()])

        pictures_by_type: defaultdict[PictureType, set[Picture]] = defaultdict(set)
        picture_sources: defaultdict[Picture, list[tuple[str, bool, int]]] = defaultdict(list)
        for filename, embedded, pictures in album_art:
            file_cover: Picture | None = None
            for picture in pictures:
                picture_sources[picture].append((filename, embedded, picture.embed_ix))
                pictures_by_type[picture.picture_type].add(picture)
                if picture.picture_type == PictureType.COVER_FRONT:
                    if file_cover is None:
                        file_cover = picture
            if embedded:
                if file_cover:
                    tracks_with_cover += 1

        front_covers: set[Picture] = pictures_by_type.get(PictureType.COVER_FRONT, set())
        cover_image_files = list(
            pic
            for pic in sorted(front_covers, key=lambda pic: pic.file_size, reverse=True)
            if any(not embedded for (_, embedded, _ix) in picture_sources[pic])
        )
        cover_image_filenames = [[file for (file, embedded, _) in picture_sources[pic] if not embedded][0] for pic in cover_image_files]
        cover_source_ix = next((ix for ix, pic in enumerate(cover_image_files) if pic.cover_source), None)
        cover_source_filename = cover_image_filenames[cover_source_ix] if cover_source_ix is not None else None

        if len(front_covers) > 1:
            cover_embedded = list(pic for pic in front_covers if any(embedded for (_, embedded, _ix) in picture_sources[pic]))
            cover_embedded_desc = [self._describe_album_art(pic, picture_sources) for pic in cover_embedded]
            table = (
                cover_image_filenames + cover_embedded_desc,
                lambda: render_image_table(self.ctx, album, cover_image_files + cover_embedded, picture_sources),
            )
            if cover_image_files and cover_source_filename is None:
                # at this point every picture in cover_image_file should be associated with exactly one file
                cover_source_candidate = self._source_image_file_candidate(cover_image_files, cover_embedded)
                options = [f"{OPTION_SELECT_COVER_IMAGE}{filename}" for filename in cover_image_filenames]
                if cover_embedded:
                    options.append(f"{OPTION_DELETE_ALL_COVER_IMAGES}{', '.join(escape(filename) for filename in cover_image_filenames)}")
                if cover_source_candidate:
                    # if there is a higher-resolution cover file, this conflict can be solved or reduced by marking that file as cover source
                    option_automatic_index = cover_image_files.index(cover_source_candidate)
                    message = "multiple cover art images: designate a high-resolution image file as cover art source"
                    if cover_embedded:
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
            # else
            if cover_source_filename is not None and len(cover_image_files) > 1:
                other_filenames = ", ".join(f for f in cover_image_filenames if f != cover_source_filename)
                option_automatic_index = 0  # YOLO

                return CheckResult(
                    ProblemCategory.PICTURES,
                    "multiple front cover image files, and one of them is marked cover source (delete others)",
                    Fixer(
                        lambda _: delete_files_except(self.ctx, cover_source_filename, album, cover_image_filenames),
                        [f'>> Keep cover source image "{cover_source_filename}" and delete other cover files: {other_filenames}'],
                        False,
                        option_automatic_index,
                        table,
                    ),
                )
            # else
            if cover_source_filename is None or len(cover_image_files) > 1 or len(cover_embedded) > 1:
                tracks_have_covers = all(any(pic for pic in track.pictures if pic.picture_type == PictureType.COVER_FRONT) for track in album.tracks)
                if tracks_have_covers:
                    # Maybe the tracks have unique cover art on purpose?
                    return CheckResult(
                        ProblemCategory.PICTURES,
                        "all tracks have cover pictures, but not all cover pictures are the same",
                        Fixer(lambda _: False, [], False, None, table),  # Don't know how to fix, but let's show the pics and the option to ignore
                    )
                # else
                return CheckResult(ProblemCategory.PICTURES, "tracks do not all have cover pictures and not all cover pictures are the same")

            # else the reason there's more than one cover is just that there's a single front cover source different from the single embedded cover
        # else only one cover
        return None

    def _describe_album_art(self, picture: Picture, picture_sources: dict[Picture, list[tuple[str, bool, int]]]):
        sources = picture_sources[picture]
        (filename, embedded, embed_ix) = sources[0]
        first_source = f"{escape(filename)}{f'#{embed_ix}' if embedded else ''}"
        details = f"{picture.format} {picture.picture_type.name}"
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
                album.picture_files[picfile].cover_source = picfile == filename
            self.ctx.console.print(f"setting cover source file to {escape(filename)}")
            operations.update_picture_files(self.ctx.db, album.album_id, album.picture_files)
            return True
        raise ValueError(f"invalid option {option}")
