import logging
import mimetypes
from collections import defaultdict
from os import rename
from typing import Any, Collection, List, Mapping, Sequence, Tuple

from rich.markup import escape

from ..database import operations
from ..interactive.image_table import render_image_table
from ..library.metadata import get_embedded_image_data
from ..types import Album, CheckResult, Fixer, Picture, PictureType, ProblemCategory
from .base_check import Check
from .helpers import FRONT_COVER_FILENAME, delete_files_except

logger = logging.getLogger(__name__)

OPTION_DELETE_ALL_COVER_IMAGES = ">> Delete all cover image files: "
OPTION_SELECT_COVER_IMAGE = ">> Mark as front cover source: "


class CheckFrontCoverSelection(Check):
    name = "front_cover_selection"
    default_config = {"enabled": True, "cover_required": False, "unique": True}
    must_pass_checks = {"duplicate_image"}

    def init(self, check_config: dict[str, Any]):
        self.cover_required = bool(check_config.get("cover_required", CheckFrontCoverSelection.default_config["cover_required"]))
        self.unique = int(check_config.get("unique", CheckFrontCoverSelection.default_config["unique"]))

    def check(self, album: Album) -> CheckResult | None:
        if album.codec() not in {"FLAC", "MP3", "Ogg Vorbis"} and self.cover_required:
            # if cover is required, only run check on albums where embedded pictures are supported
            return None

        tracks_with_cover = 0
        issues: set[str] = set()
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
        front_cover_image_files = list(
            pic
            for pic in sorted(front_covers, key=lambda pic: pic.file_size, reverse=True)
            if any(not embedded for (_, embedded, _ix) in picture_sources[pic])
        )
        cover_image_filenames = [[file for (file, embedded, _) in picture_sources[pic] if not embedded][0] for pic in front_cover_image_files]
        cover_source_ix = next((ix for ix, pic in enumerate(front_cover_image_files) if pic.front_cover_source), None)
        cover_source_filename = cover_image_filenames[cover_source_ix] if cover_source_ix is not None else None

        if self.unique and len(front_covers) > 1:
            front_cover_embedded = list(pic for pic in front_covers if any(embedded for (_, embedded, _ix) in picture_sources[pic]))
            cover_embedded_desc = [self._describe_album_art(pic, picture_sources) for pic in front_cover_embedded]
            table = (
                cover_image_filenames + cover_embedded_desc,
                lambda: render_image_table(self.ctx, album, front_cover_image_files + front_cover_embedded, picture_sources),
            )
            if front_cover_image_files and cover_source_filename is None:
                # at this point every picture in front_cover_image_file should be associated with exactly one file
                cover_source_candidate = self._source_image_file_candidate(front_cover_image_files, front_cover_embedded)
                options = [f"{OPTION_SELECT_COVER_IMAGE}{filename}" for filename in cover_image_filenames]
                if front_cover_embedded:
                    options.append(f"{OPTION_DELETE_ALL_COVER_IMAGES}{', '.join(escape(filename) for filename in cover_image_filenames)}")
                if cover_source_candidate:
                    # if there is a higher-resolution cover file, this conflict can be solved or reduced by marking that file as cover source
                    option_automatic_index = front_cover_image_files.index(cover_source_candidate)
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
            elif cover_source_filename is not None and len(front_cover_image_files) > 1:
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
            elif cover_source_filename is None or len(front_cover_image_files) > 1 or len(front_cover_embedded) > 1:
                # TODO if multiple front cover embedded but every track has one, even if they are different that's probably on purpose?
                issues.add("COVER_FRONT pictures are not all the same")
                # no automatic fixer yet, but this shows the issue:
                # return CheckResult(ProblemCategory.PICTURES, "COVER_FRONT not all the same", Fixer(lambda _: False, [], False, None, table))

        if not front_covers:
            if pictures_by_type:
                pics = [k for k, _ in picture_sources.items()]
                headers = [self._describe_album_art(pic, picture_sources) for pic in pics]
                table = (headers, lambda: render_image_table(self.ctx, album, pics, picture_sources))
                has_embedded = any(track.pictures for track in album.tracks)
                option_automatic_index = 0 if len(headers) == 1 else None
                message = f"album has pictures but none is COVER_FRONT picture{' (embedded)' if has_embedded else ''}"
                return CheckResult(
                    ProblemCategory.PICTURES,
                    message,
                    Fixer(
                        lambda option: self._fix_set_cover(album, option, headers, pics, picture_sources),
                        headers,
                        False,
                        option_automatic_index,
                        table,
                        "Select an image to be renamed or extracted to cover.jpg/cover.png/cover.gif",
                    ),
                )
            elif self.cover_required:
                # TODO there are no pictures available, check cannot pass. someday [use external tool to] retrieve cover art?
                issues.add("album does not have a COVER_FRONT picture or any other pictures to use")

        if issues:
            return CheckResult(ProblemCategory.PICTURES, ", ".join(list(issues)))

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
                album.picture_files[picfile].front_cover_source = picfile == filename
            self.ctx.console.print(f"setting cover source file to {escape(filename)}")
            operations.update_picture_files(self.ctx.db, album.album_id, album.picture_files)
            return True
        raise ValueError(f"invalid option {option}")

    def _fix_set_cover(
        self, album: Album, option: str, options: list[str], pics: list[Picture], sources: Mapping[Picture, List[Tuple[str, bool, int]]]
    ):
        ix = options.index(option)
        pic = pics[ix]
        file_sources = [filename for filename, embedded, _ in sources[pic] if not embedded]
        if file_sources:
            path = self.ctx.config.library / album.path / file_sources[0]
            new_filename = f"{FRONT_COVER_FILENAME}{path.suffix}"
            self.ctx.console.print(f"Renaming {file_sources[0]} to {new_filename}")
            rename(path, self.ctx.config.library / album.path / new_filename)
        else:
            (filename, _, embed_ix) = sources[pic][0]
            path = self.ctx.config.library / album.path / filename
            images = get_embedded_image_data(path)
            image_data = images[embed_ix]
            suffix = mimetypes.guess_extension(pic.format)
            new_filename = f"{FRONT_COVER_FILENAME}{suffix}"
            self.ctx.console.print(f"Creating {len(image_data)} byte {pic.format} file {new_filename}")
            new_path = self.ctx.config.library / album.path / new_filename
            if new_path.exists():
                self.ctx.console.print(f"Error: the file {escape(str(new_path))} already exists (scan again)")
                raise SystemExit(1)
            with open(new_path, "wb") as f:
                f.write(image_data)

        return True
