import logging
from os import unlink
from pathlib import Path
from typing import Sequence

from rich.console import RenderableType
from rich.markup import escape

from ...picture.format import SUPPORTED_IMAGE_SUFFIXES
from ...tagger.folder import Cap
from ...types import Album, CheckResult, Fixer
from ..base_check import Check

logger = logging.getLogger(__name__)


class CheckInvalidImage(Check):
    name = "invalid-image"
    default_config = {"enabled": True}

    def check(self, album: Album) -> CheckResult | None:
        album_art = [(track.filename, track.pictures) for track in album.tracks]
        album_art.extend([(file.filename, [file.to_picture()]) for file in album.picture_files])
        table_rows: Sequence[Sequence[RenderableType]] = []
        issues: set[str] = set()
        any_bad_image_files = False
        any_bad_embedded_images = False
        for source_filename, pictures in album_art:
            for picture in pictures:
                load_issue = dict(picture.picture_info.load_issue)
                if picture.picture_info.load_issue and "error" in load_issue:
                    error = str(load_issue["error"])
                    table_rows.append([source_filename, picture.type.name, error])
                    issues.add(error)
                    embedded = Path(source_filename).suffix not in SUPPORTED_IMAGE_SUFFIXES
                    any_bad_embedded_images |= embedded
                    any_bad_image_files |= not embedded
        if issues:
            return CheckResult(
                f"image load errors: {', '.join(issues)}",
                Fixer(
                    lambda _: self._fix_remove_bad_images(album),
                    [">> Remove/delete all invalid images"],
                    False,
                    None,
                    (["File", "Type", "Error"], table_rows),
                ),
            )

    def _fix_remove_bad_images(self, album: Album):
        changed = False
        for file in album.picture_files:
            load_issue = dict(file.picture_info.load_issue)
            if "error" in load_issue:
                self.ctx.console.print(f"Deleting image file {escape(file.filename)}")
                path = self.ctx.config.library / album.path / file.filename
                unlink(path)
                changed = True

        tagger = self.tagger.get(album.path)
        for track in album.tracks:
            for pic in track.pictures:
                load_issue = dict(pic.picture_info.load_issue)
                if "error" in load_issue:
                    if tagger.supports(track.filename, Cap.PICTURES):
                        with tagger.open(track.filename) as tags:
                            for file in [pic for pic, _data in tags.get_pictures() if (any(k == "error" for k, _ in pic.picture_info.load_issue))]:
                                self.ctx.console.print(f"Removing {file.type.name} embedded image from {escape(track.filename)}")
                                tags.remove_picture(file)
                                changed = True
                    else:
                        logger.warning(f"cannot remove embedded image from {track.filename} because file type not supported yet")

        return changed
