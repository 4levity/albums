import logging
from os import unlink
from typing import Sequence

from rich.console import RenderableType
from rich.markup import escape

from ...types import Album, CheckResult, Fixer, ProblemCategory
from ..base_check import Check

logger = logging.getLogger(__name__)


class CheckInvalidImage(Check):
    name = "invalid-image"
    default_config = {"enabled": True}

    def check(self, album: Album) -> CheckResult | None:
        album_art = [(track.filename, True, track.pictures) for track in album.tracks]
        album_art.extend([(filename, False, [picture]) for filename, picture in album.picture_files.items()])
        table_rows: Sequence[Sequence[RenderableType]] = []
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

        tagger = self.tagger.get(album.path)
        for track in album.tracks:
            if any(pic.load_issue and "error" in pic.load_issue for pic in track.pictures):
                if tagger.supports(track.filename):
                    with tagger.open(track.filename) as tags:
                        for pic in [pic for pic, _data in tags.get_pictures() if (any(k == "error" for k, _ in pic.load_issue))]:
                            self.ctx.console.print(f"Removing {pic.picture_type.name} embedded image from {escape(track.filename)}")
                            tags.remove_picture(pic)
                            changed = True
                else:
                    logger.warning(f"cannot remove embedded image from {track.filename} because file type not supported yet")

        return changed
