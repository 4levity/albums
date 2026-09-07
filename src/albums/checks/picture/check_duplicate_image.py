import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Final

from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.checks.helpers import delete_files_except
from albums.entities import Album
from albums.interactive import render_image_table
from albums.picture import SUPPORTED_IMAGE_SUFFIXES
from albums.tagger import Cap, Picture, PictureType
from albums.words import plural

logger: Final = logging.getLogger(__name__)


class CheckDuplicateImage(Check):
    name = "duplicate-image"
    default_config = {"enabled": True, "cover_only": False}
    must_pass_checks = {"invalid-image"}

    def init(self, check_config: dict[str, Any]):
        self.cover_only = bool(check_config.get("cover_only", CheckDuplicateImage.default_config["cover_only"]))

    def check(self, album: Album) -> CheckResult | None:
        album_art = [(track.filename, True, [p.to_picture() for p in track.pictures]) for track in album.tracks]
        album_art.extend([(file.filename, False, [file.to_picture()]) for file in album.picture_files])

        pictures_by_type: defaultdict[PictureType, set[Picture]] = defaultdict(set)
        picture_sources: defaultdict[Picture, list[str]] = defaultdict(list)
        duplicate_embedded: list[tuple[str, Picture]] = []
        for filename, embedded, pictures in album_art:
            file_pics_by_content: defaultdict[Picture, list[Picture]] = defaultdict(list)
            for picture in pictures:
                if picture.type != PictureType.COVER_FRONT and self.cover_only:
                    continue
                picture_sources[picture].append(filename)
                pictures_by_type[picture.type].add(picture)
                if embedded:
                    file_pics_by_content[picture].append(picture)

            # if the same picture is embedded more than once in one track, flag it for removal (keep the first)
            for unique_picture in file_pics_by_content:
                if len(file_pics_by_content[unique_picture]) > 1:
                    # TODO: allow duplicate image data if configured and if the picture_type is not the same
                    duplicate_embedded.append((filename, unique_picture))

        if duplicate_embedded:
            pic_types = ", ".join(sorted(set(pic.type.name for _, pic in duplicate_embedded)))
            tagger = self.tagger.get(album.path)
            read_only_files = sorted({filename for filename, _ in duplicate_embedded if not tagger.supports(filename, Cap.PICTURES)})
            fixable = [(filename, pic) for filename, pic in duplicate_embedded if tagger.supports(filename, Cap.PICTURES)]
            message = f"duplicate embedded image data in one or more files: {pic_types}"
            if read_only_files:
                message += f" - cannot update {', '.join(escape(filename) for filename in read_only_files)} (WMA/ASF embedded images are read-only)"
            if fixable:
                # identical image data, so removing the extra copies is lossless
                return CheckResult(
                    message,
                    Fixer(
                        lambda _: self._fix_remove_duplicate_embedded(album, fixable),
                        [">> Remove duplicate embedded images (keep the first)"],
                        False,
                        0,
                    ),
                )
            return CheckResult(message)

        # image files that are exact duplicates of each other are not useful, keep one and delete the rest
        # (front covers only when cover_only, all picture types otherwise)
        picture_types = [PictureType.COVER_FRONT] + [t for t in PictureType if t is not PictureType.COVER_FRONT]
        if self.cover_only:
            picture_types = picture_types[:1]

        def image_file_sources(pic: Picture) -> list[str]:
            return sorted(filename for filename in picture_sources[pic] if str.lower(Path(filename).suffix) in SUPPORTED_IMAGE_SUFFIXES)

        # the cover_source mark only survives a rescan by filename, so keep the marked file when choosing which duplicate to delete
        cover_source_filename = next((file.filename for file in album.picture_files if file.cover_source), None)

        for pic_type in picture_types:
            for pic in sorted((c for c in pictures_by_type.get(pic_type, set()) if image_file_sources(c)), key=lambda c: image_file_sources(c)[0]):
                filenames = image_file_sources(pic)
                if len(filenames) > 1:
                    table = (
                        [escape(filename) for filename in filenames],
                        lambda: render_image_table(self.ctx, self.tagger.get(album.path), [pic] * len(filenames), picture_sources),
                    )
                    if cover_source_filename in filenames:  # prefer the cover source file, otherwise pick the shortest filename
                        option_automatic_index = filenames.index(cover_source_filename)
                    else:
                        option_automatic_index = filenames.index(min(filenames, key=lambda s: len(s)))
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
        return None

    def _fix_remove_duplicate_embedded(self, album: Album, duplicate_embedded: list[tuple[str, Picture]]) -> FixResult:
        tagger = self.tagger.get(album.path)
        changed = False
        for filename, picture in duplicate_embedded:
            with tagger.open(filename) as tag:
                copies = [(pic, data) for pic, data in tag.get_pictures() if pic == picture]
                if len(copies) < 2:
                    continue
                (kept_pic, kept_data) = copies[0]
                self.ctx.console.print(f"Removing {plural(len(copies) - 1, f'duplicate {picture.type.name} image')} from {escape(filename)}")
                # remove_picture removes every matching picture, so remove all copies and re-add the first one
                tag.remove_picture(kept_pic)
                tag.add_picture(kept_pic, kept_data)
                changed = True
        return FixResult.of(changed)
