import logging
import mimetypes
from collections import defaultdict
from glob import iglob
from os import rename
from pathlib import Path
from shutil import which
from string import Template
from subprocess import run
from typing import Any, Dict, Final, List, Mapping, Sequence

from rich.markup import escape

from albums.checks.picture.check_cover_dimensions import CheckCoverDimensions

from ...interactive.image_table import render_image_table
from ...library.tag_tools import get_album_name_from_tags, get_artist_from_tags
from ...picture.format import SUPPORTED_IMAGE_SUFFIXES
from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import Picture, PictureType
from ...types import Album, CheckResult, Fixer, FixResult
from ..base_check import Check
from ..helpers import FRONT_COVER_FILENAME
from ..path.check_cover_filename import CheckCoverFilename, parse_config_cover_filename

logger: Final = logging.getLogger(__name__)


class CheckCoverAvailable(Check):
    name = "cover-available"
    default_config = {"enabled": True, "cover_required": False, "get_cover_command": ""}
    must_pass_checks = {"duplicate-image"}

    def init(self, check_config: dict[str, Any]):
        self.cover_required = bool(check_config.get("cover_required", self.default_config["cover_required"]))

        # borrow filename pattern from CheckCoverFilename
        self.filename_pattern = str(self.ctx.config.checks[CheckCoverFilename.name].get("filename", CheckCoverFilename.default_config["filename"]))

        cmd_str = str(check_config.get("get_cover_command", self.default_config["get_cover_command"]))
        if not cmd_str and which("sacad") and which("sacad_r"):  # default = Smart Automatic Cover Art Downloader - https://github.com/desbma/sacad
            # for default sacad config, don't target larger than configured max in cover-dimensions check
            max_size = self.ctx.config.checks[CheckCoverDimensions.name].get("max_pixels", CheckCoverDimensions.default_config["max_pixels"])
            target_size = min(1200, int(str(max_size)))
            cmd_str = f"sacad --preserve-format --size-tolerance 60 $artist $album {target_size} $filename"

        self.get_cover_command = [Template(part) for part in cmd_str.split(" ")] if cmd_str else []
        for id in (id for part in self.get_cover_command for id in part.get_identifiers() if id not in {"artist", "album", "filename", "path"}):
            raise ValueError(f"invalid substitution '{id}' in cover-available.get_cover_command")

    def check(self, album: Album) -> CheckResult | None:
        if self.cover_required and not all(AlbumTagger.supports(track.filename, Cap.PICTURES) for track in album.tracks):
            return None  # if cover is required, only run check on albums where embedded pictures are supported

        album_art = [(track.filename, [p.to_picture() for p in track.pictures]) for track in album.tracks]
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
            elif self.cover_required:
                artist_name = get_artist_from_tags(album)
                album_name = get_album_name_from_tags(album)
                if self.get_cover_command and artist_name and album_name:
                    command_preview = self._preview_get_cover_command(album, artist_name, album_name)
                    options = [f">> Try to retrieve cover image with: {command_preview}"]
                    option_automatic_index = 0
                    return CheckResult(
                        "album does not have any pictures to use as cover art, can try searching",
                        Fixer(lambda _: self._fix_retrieve_cover(album, artist_name, album_name), options, False, option_automatic_index),
                    )
                return CheckResult("album does not have any pictures to use as cover art, and cannot search because artist/album not known")
            # else no pictures available + not required
        # else front cover image(s) available
        return None

    def _describe_album_art(self, picture: Picture, picture_sources: Dict[Picture, List[str]]):
        sources = picture_sources[picture]
        filename = sources[0]
        first_source = f"{escape(filename)}"
        details = f"{picture.picture_info.mime_type} {picture.type.name}"
        return f"{first_source}{f' (and {len(sources) - 1} more)' if len(sources) > 1 else ''} {details}"

    def _fix_set_cover(self, album: Album, option: str, options: list[str], pics: list[Picture], sources: Mapping[Picture, Sequence[str]]):
        ix = options.index(option)
        pic = pics[ix]
        file_sources = [filename for filename in sources[pic] if str.lower(Path(filename).suffix) in SUPPORTED_IMAGE_SUFFIXES]
        if file_sources:
            path = self.ctx.config.library / album.path / file_sources[0]
            new_filename = f"{FRONT_COVER_FILENAME}{path.suffix}"
            self.ctx.console.print(f"Renaming {escape(file_sources[0])} to {escape(new_filename)}", highlight=False)
            rename(path, self.ctx.config.library / album.path / new_filename)
        else:
            filename = sources[pic][0]
            with self.tagger.get(album.path).open(filename) as tags:
                image_data = tags.get_image_data(pic)
            suffix = mimetypes.guess_extension(pic.picture_info.mime_type)
            new_filename = f"{FRONT_COVER_FILENAME}{suffix}"
            self.ctx.console.print(f"Creating {len(image_data)} byte {pic.picture_info.mime_type} file {escape(new_filename)}", highlight=False)
            new_path = self.ctx.config.library / album.path / new_filename
            if new_path.exists():
                self.ctx.console.print(f"Error: the file {escape(str(new_path))} already exists (scan again)")
                raise SystemExit(1)
            with open(new_path, "wb") as f:
                f.write(image_data)

        return FixResult.CHANGED_ALBUM

    def _fix_retrieve_cover(self, album: Album, artist_name: str, album_name: str):
        command = self._generate_get_cover_command(album, artist_name, album_name)
        expect_pattern = str(self.ctx.config.library / album.path / self.filename_pattern)
        if any(iglob(expect_pattern)):
            logger.error(f"_fix_get_cover was called but there is already a file at {expect_pattern}")
            return FixResult.NO_CHANGE

        self.ctx.console.print(f"Trying to retrieve album cover with: {escape(' '.join(command))}")
        result = run(command, cwd=(self.ctx.config.library / album.path))
        if not any(iglob(expect_pattern)):
            if result.returncode == 0:
                logger.warning(f"external program returned exit code 0 (success) but file {expect_pattern} was not found")
            self.ctx.console.print("album cover not found")
            return FixResult.NO_CHANGE

        if result.returncode != 0:
            logger.warning(
                f"external program returned nonzero exit code {result.returncode} indicating failure, but file {expect_pattern} does exist"
            )
        self.ctx.console.print("album cover successfully downloaded")
        return FixResult.CHANGED_ALBUM

    def _preview_get_cover_command(self, album: Album, artist_name: str, album_name: str) -> str:
        subs = {
            "artist": f'"{artist_name}"',
            "album": f'"{album_name}"',
            "filename": f'"{self._get_filename()}"',
            "path": f'"{str(self.ctx.config.library / album.path)}"',
        }
        return " ".join(part.safe_substitute(subs) for part in self.get_cover_command)

    def _generate_get_cover_command(self, album: Album, artist_name: str, album_name: str) -> List[str]:
        subs = {
            "artist": artist_name,
            "album": album_name,
            "filename": self._get_filename(),
            "path": f"{str(self.ctx.config.library / album.path)}",
        }
        return [part.safe_substitute(subs) for part in self.get_cover_command]

    def _get_filename(self):
        (stem, suffix) = parse_config_cover_filename(self.filename_pattern)
        if suffix is None:
            return f"{stem}.png"  # note: sacad will ignore suffix with --preserve-format option
        return f"{stem}.{suffix}"
