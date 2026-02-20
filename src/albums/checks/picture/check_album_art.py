import logging
from typing import Any

import humanize

from ...types import Album, CheckResult, ProblemCategory
from ..base_check import Check

logger = logging.getLogger(__name__)


class CheckAlbumArt(Check):
    name = "album-art"
    default_config = {
        "enabled": True,
        "embedded_size_max": 8 * 1024 * 1024,  # up to 16 MB is OK in ID3v2
    }
    must_pass_checks = {"invalid-image"}

    def init(self, check_config: dict[str, Any]):
        self.embedded_size_max = int(check_config.get("embedded_size_max", CheckAlbumArt.default_config["embedded_size_max"]))

    def check(self, album: Album) -> CheckResult | None:
        issues: set[str] = set()
        album_art = [(track.filename, True, track.pictures) for track in album.tracks]
        album_art.extend([(filename, False, [picture]) for filename, picture in album.picture_files.items()])

        for _filename, embedded, pictures in album_art:
            for picture in pictures:
                if embedded:
                    if picture.format not in {"image/png", "image/jpeg"}:
                        # TODO: extract original to file, then automatically convert to jpg
                        issues.add(f"embedded image {picture.picture_type.name} is not a recommended format ({picture.format})")
                    if picture.file_size > self.embedded_size_max:
                        # TODO: extract original to file, then resize/compress
                        file_size = humanize.naturalsize(picture.file_size, binary=True)
                        file_size_max = humanize.naturalsize(self.embedded_size_max, binary=True)
                        issues.add(f"embedded image {picture.picture_type.name} is over the configured limit ({file_size} > {file_size_max})")
            # TODO apply other configurable rules to all album art

        if issues:
            return CheckResult(ProblemCategory.PICTURES, ", ".join(list(issues)))
