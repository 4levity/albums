import logging
from os import unlink
from typing import List

from rich.console import RenderableType
from rich.markup import escape

from albums.library.metadata import remove_embedded_image

from ..types import Album
from .base_check import Check, CheckResult, Fixer, ProblemCategory

logger = logging.getLogger(__name__)

OPTION_DELETE_ALL_COVER_IMAGES = ">> Delete all cover image files: "
OPTION_SELECT_COVER_IMAGE = ">> Mark as front cover source: "


class CheckInvalidImage(Check):
    name = "invalid_image"
    default_config = {"enabled": True}

    def check(self, album: Album) -> CheckResult | None:
        album_art = [(track.filename, True, track.pictures) for track in album.tracks]
        album_art.extend([(filename, False, [picture]) for filename, picture in album.picture_files.items()])
        table_rows: List[List[RenderableType]] = []
        issues: set[str] = set()
        any_bad_image_files = False
        any_bad_embedded_images = False
        for filename, embedded, pictures in album_art:
            for picture in pictures:
                if picture.load_issue and "error" in picture.load_issue:
                    source = f"{filename}{f'#{picture.embed_ix}' if embedded else ''}"
                    error = str(picture.load_issue["error"])
                    table_rows.append([source, picture.picture_type.name, error])
                    issues.add(error)
                    any_bad_embedded_images |= embedded
                    any_bad_image_files |= not embedded
        if issues:
            return CheckResult(
                ProblemCategory.PICTURES,
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
        for filename, pic in album.picture_files.items():
            if pic.load_issue and "error" in pic.load_issue:
                self.ctx.console.print(f"Deleting image file {escape(filename)}")
                path = self.ctx.config.library / album.path / filename
                unlink(path)
                changed = True
        for track in album.tracks:
            for pic in track.pictures:
                if pic.load_issue and "error" in pic.load_issue:
                    if track.stream and track.stream.codec:
                        if track.stream.codec in {"FLAC", "Ogg Vorbis", "MP3"}:
                            self.ctx.console.print(f"Removing {pic.picture_type.name} embedded image #{pic.embed_ix} from {escape(track.filename)}")
                            path = self.ctx.config.library / album.path / track.filename
                            changed |= remove_embedded_image(path, track.stream.codec, pic)
                        else:
                            logger.warning(f"cannot remove embedded image from {track.filename} because {track.stream.codec} not supported yet")
                    else:
                        logger.warning(f"cannot remove embedded image from {track.filename} because track.stream.codec is not set")

        return changed
