import logging
from os import unlink
from pathlib import Path
from typing import List

from rich.console import RenderableType
from rich.markup import escape

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
                    # normally wouldn't include filename in issue list but user can't see table for embedded files until there is a fixer
                    # TODO: consider removing source filename when this check has a fixer for embedded corrupt images
                    issues.add(error + (f' "{source}"' if embedded else ""))
                    any_bad_embedded_images |= embedded
                    any_bad_image_files |= not embedded
        if issues:
            if any_bad_image_files:
                fixer = Fixer(
                    lambda _: self._fix_delete_error_images(album),
                    [f">> Remove/delete the invalid image files{' (embedded fix not available yet)' if any_bad_embedded_images else ''}"],
                    False,
                    None,
                    (["File", "Type", "Error"], table_rows),
                )
            else:
                fixer = None  # TODO support for embedded also, see below
            return CheckResult(ProblemCategory.PICTURES, f"image load errors: {', '.join(issues)}", fixer)

    def _fix_delete_error_images(self, album: Album):
        changed = False
        for filename, pic in album.picture_files.items():
            if pic.load_issue and "error" in pic.load_issue:
                self.ctx.console.print(f"Deleting image file {escape(filename)}")
                path = self.ctx.library_root if self.ctx.library_root else Path(".") / album.path / filename
                unlink(path)
                changed = True
        # for track in album.tracks:
        #     for pic in track.pictures:
        #         if pic.load_issue and "error" in pic.load_issue:
        #             self.ctx.console.print(f"Deleting {pic.picture_type.name} embedded image #{pic.embed_ix} from {escape(track.filename)}")
        #             album_path = self.ctx.library_root if self.ctx.library_root else Path(".") / album.path
        #             changed |= self._remove_embedded_image(album_path, track, pic)
        return changed

    # def _remove_embedded_image(self, album_path: Path, track: Track, pic: Picture):
    #     if track.stream and track.stream.codec == "FLAC":
    #         return self._remove_embedded_image_flac(album_path / track.filename, pic)
    #     if track.stream and track.stream.codec == "MP3":
    #         return self._remove_embedded_image_mp3(album_path / track.filename, pic)
    #     logger.warning(f"cannot remove embedded image from {track.filename}")
    #     return False

    # def _remove_embedded_image_flac(self, track_path: Path, pic: Picture):
    #     # TODO implement, see also embedded_picture_metadata
    #     return False

    # def _remove_embedded_image_mp3(self, track_path: Path, pic: Picture):
    #     # TODO this is gonna be a little tricky
    #     return False
