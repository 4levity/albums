import logging
import mimetypes
from collections import defaultdict
from os import rename
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from rich.markup import escape

from ...database.models import AlbumEntity
from ...interactive.image_table import render_image_table
from ...picture.format import SUPPORTED_IMAGE_SUFFIXES
from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import Picture, PictureType
from ...types import CheckResult, Fixer
from ..base_check import Check
from ..helpers import FRONT_COVER_FILENAME

logger = logging.getLogger(__name__)


class CheckCoverAvailable(Check):
    name = "cover-available"
    default_config = {"enabled": True, "cover_required": False}
    must_pass_checks = {"duplicate-image"}

    def init(self, check_config: dict[str, Any]):
        self.cover_required = bool(check_config.get("cover_required", CheckCoverAvailable.default_config["cover_required"]))

    def check(self, album: AlbumEntity) -> CheckResult | None:
        if self.cover_required and not all(AlbumTagger.supports(track.filename, Cap.PICTURES) for track in album.tracks):
            return None  # if cover is required, only run check on albums where embedded pictures are supported

        album_art = [(track.filename, track.pictures) for track in album.tracks]
        album_art.extend([(file.filename, [file.to_picture()]) for file in album.picture_files])

        pictures_by_type: defaultdict[PictureType, set[Picture]] = defaultdict(set)
        picture_sources: Dict[Picture, List[str]] = defaultdict(list)
        for filename, pictures in album_art:
            for picture in pictures:
                picture_sources[picture].append(filename)
                pictures_by_type[picture.type].add(picture)

        front_covers: set[Picture] = pictures_by_type.get(PictureType.COVER_FRONT, set())
        if not front_covers:
            if pictures_by_type:
                pics = [k for k, _ in picture_sources.items()]
                headers = [self._describe_album_art(pic, picture_sources) for pic in pics]
                table = (headers, lambda: render_image_table(self.ctx, self.tagger.get(album.path), pics, picture_sources))
                has_embedded = any(track.pictures for track in album.tracks)
                option_automatic_index = 0 if len(headers) == 1 else None
                message = f"album has pictures but none is COVER_FRONT picture{' (embedded)' if has_embedded else ''}"
                return CheckResult(
                    message,
                    Fixer(
                        lambda option: self._fix_set_cover(album, option, headers, pics, picture_sources),
                        headers,
                        False,
                        option_automatic_index,
                        table,
                        "Select an image to be renamed or extracted to cover.jpg/cover.png/etc",
                    ),
                )
            # else
            if self.cover_required:
                # TODO [use external tool to] retrieve cover art?
                return CheckResult("album does not have a COVER_FRONT picture or any other pictures to use")
            # else no pictures available + not required
        # else front cover image(s) available
        return None

    def _describe_album_art(self, picture: Picture, picture_sources: Dict[Picture, List[str]]):
        sources = picture_sources[picture]
        filename = sources[0]
        first_source = f"{escape(filename)}"
        details = f"{picture.picture_info.mime_type} {picture.type.name}"
        return f"{first_source}{f' (and {len(sources) - 1} more)' if len(sources) > 1 else ''} {details}"

    def _fix_set_cover(self, album: AlbumEntity, option: str, options: list[str], pics: list[Picture], sources: Mapping[Picture, Sequence[str]]):
        ix = options.index(option)
        pic = pics[ix]
        file_sources = [filename for filename in sources[pic] if Path(filename).suffix in SUPPORTED_IMAGE_SUFFIXES]
        if file_sources:
            path = self.ctx.config.library / album.path / file_sources[0]
            new_filename = f"{FRONT_COVER_FILENAME}{path.suffix}"
            self.ctx.console.print(f"Renaming {file_sources[0]} to {new_filename}")
            rename(path, self.ctx.config.library / album.path / new_filename)
        else:
            filename = sources[pic][0]
            with self.tagger.get(album.path).open(filename) as tags:
                image_data = tags.get_image_data(pic)
            suffix = mimetypes.guess_extension(pic.picture_info.mime_type)
            new_filename = f"{FRONT_COVER_FILENAME}{suffix}"
            self.ctx.console.print(f"Creating {len(image_data)} byte {pic.picture_info.mime_type} file {new_filename}")
            new_path = self.ctx.config.library / album.path / new_filename
            if new_path.exists():
                self.ctx.console.print(f"Error: the file {escape(str(new_path))} already exists (scan again)")
                raise SystemExit(1)
            with open(new_path, "wb") as f:
                f.write(image_data)

        return True
