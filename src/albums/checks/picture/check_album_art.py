import logging
import mimetypes
from collections import defaultdict
from typing import Any, Mapping

import humanize

from albums.checks.helpers import FRONT_COVER_FILENAME
from albums.interactive.image_table import render_image_table

from ...tagger.types import Picture, PictureType
from ...types import Album, CheckResult, Fixer
from ..base_check import Check

logger = logging.getLogger(__name__)


class CheckAlbumArt(Check):
    name = "album-art"
    default_config = {
        "enabled": True,
        "embedded_size_max": 4 * 1024 * 1024,  # up to 16 MB is OK in ID3v2
        # TODO rules for non-embedded album art
    }
    must_pass_checks = {"invalid-image"}

    def init(self, check_config: dict[str, Any]):
        self.embedded_size_max = int(check_config.get("embedded_size_max", CheckAlbumArt.default_config["embedded_size_max"]))

    def check(self, album: Album) -> CheckResult | None:
        picture_sources: defaultdict[Picture, list[str]] = defaultdict(list)
        bad_formats: list[str] = []
        bad_file_sizes = 0
        largest_bad_file_size = 0
        for track in album.tracks:
            for picture in track.pictures:
                if picture.file_info.mime_type not in {"image/png", "image/jpeg"}:
                    picture_sources[picture].append(track.filename)
                    bad_formats.append(picture.file_info.mime_type)
                if picture.file_info.file_size > self.embedded_size_max:
                    picture_sources[picture].append(track.filename)
                    largest_bad_file_size = max(largest_bad_file_size, picture.file_info.file_size)
                    bad_file_sizes += 1

        if picture_sources:
            issues: list[str] = []
            if bad_formats:
                issues.append(f"embedded images ({len(bad_formats)}) not in recommended format ({', '.join(set(bad_formats))})")
            if bad_file_sizes:
                file_size = humanize.naturalsize(largest_bad_file_size, binary=True)
                file_size_max = humanize.naturalsize(self.embedded_size_max, binary=True)
                issues.append(f"embedded images ({bad_file_sizes}) over the size limit (largest {file_size} > {file_size_max})")
            options = [">> Extract images to files and remove embedded"]
            option_automatic_index = 0
            extract = list(picture_sources.items())
            table = (
                [f"{pic.type.name} in {len(refs)} files" for pic, refs in extract],
                lambda: render_image_table(self.ctx, self.tagger.get(album.path), [pic for pic, _ in extract], picture_sources),
            )
            return CheckResult(
                ", ".join(list(issues)),
                Fixer(
                    lambda _: self._fix_extract(album, picture_sources),
                    options,
                    False,
                    option_automatic_index,
                    table,
                ),
            )

    def _fix_extract(self, album: Album, embedded_to_extract: Mapping[Picture, list[str]]):
        tagger = self.tagger.get(album.path)
        for pic, refs in embedded_to_extract.items():
            filename = refs[0]
            stem = FRONT_COVER_FILENAME if pic.type == PictureType.COVER_FRONT else str.lower(pic.type.name)
            suffix = mimetypes.guess_extension(pic.file_info.mime_type)
            num = 0
            while (new_file := (self.ctx.config.library / album.path / f"{stem}{f'{num}' if num else ''}{suffix}")) and new_file.exists():
                num += 1

            self.ctx.console.print(f"Extracting {pic.type.name} {pic.file_info.mime_type} from {filename} to {new_file.name}")
            with tagger.open(filename) as tags:
                image_data = tags.get_image_data(pic)
            with open(new_file, "wb") as f:
                f.write(image_data)
            for filename in refs:
                with tagger.open(filename) as tags:
                    self.ctx.console.print(f"Removing {pic.type.name} {pic.file_info.mime_type} from {filename}")
                    tags.remove_picture(pic)

        return True
