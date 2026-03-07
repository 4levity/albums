import io
from os import rename, unlink
from pathlib import Path
from typing import Any

from PIL import Image

from albums.library.folder import read_binary_file

from ...database.operations import update_picture_files
from ...tagger.types import PictureType
from ...types import Album, CheckResult, Fixer, PictureFile
from ..base_check import Check


class CheckCoverFilename(Check):
    name = "cover-filename"
    default_config = {"enabled": True, "filename": "cover.*", "jpeg_quality": 90}

    def init(self, check_config: dict[str, Any]):
        filename = str(check_config.get("filename", CheckCoverFilename.default_config["filename"]))
        parts = filename.split(".")
        if len(parts) != 2:
            raise ValueError('cover-filename.filename must be in the form "filename.suffix"')
        self.stem = parts[0]
        suffix = parts[1]
        if str.lower(suffix) not in {"*", "png", "jpg"}:
            raise ValueError('cover-filename.filename suffix must be "*" or "jpg" or "png"')
        match suffix:
            case "jpg":
                self.suffix = f".{suffix}"
            case "png":
                self.suffix = f".{suffix}"
            case _:
                self.suffix = None
        self.jpeg_quality = int(check_config.get("jpeg_quality", CheckCoverFilename.default_config["jpeg_quality"]))
        if self.jpeg_quality < 1 or self.jpeg_quality > 95:
            raise ValueError("cover-filename.jpeg_quality must be between 1 and 95")

    def check(self, album: Album):
        if album.picture_files and not any(self._matches(file.filename, True) for file in album.picture_files):
            cover_files = [file.filename for file in album.picture_files if PictureType.from_filename(file.filename) == PictureType.COVER_FRONT]
            if not cover_files:
                return None  # none of the image filenames are recognized as cover images
            if len(cover_files) > 1:
                return CheckResult(
                    f"multiple cover image files, don't know which to rename: {', '.join(sorted(cover_files))}",
                )

            path = Path(cover_files[0])
            new_filename = f"{self.stem}{self.suffix if self.suffix else path.suffix}"
            if self.suffix and str.lower(self.suffix) != str.lower(path.suffix):
                # file has to be converted
                options = [f">> Convert {cover_files[0]} to {new_filename}"]
                option_automatic_index = 0
                return CheckResult(
                    f"cover image has the wrong filename and type (expected {self.suffix}): {cover_files[0]}",
                    Fixer(
                        lambda _: self._fix_convert_cover(album, cover_files[0]),
                        options,
                        False,
                        option_automatic_index,
                    ),
                )

            # else just rename, no conversion
            options = [f">> Rename {cover_files[0]} to {new_filename}"]
            option_automatic_index = 0
            return CheckResult(
                f"cover image has the wrong filename: {cover_files[0]}",
                Fixer(
                    lambda _: self._fix_rename_cover(album, cover_files[0], new_filename),
                    options,
                    False,
                    option_automatic_index,
                ),
            )
        return None

    def _fix_convert_cover(self, album: Album, cover_file: str):
        album_path = self.ctx.config.library / album.path
        image_data = read_binary_file(album_path / cover_file)
        image = Image.open(io.BytesIO(image_data))
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        unlink(album_path / cover_file)  # delete first, in case this is a case-insensitive file system and the names differ only by case
        new_filename = f"{self.stem}{self.suffix}"
        image.save(album_path / new_filename, quality=self.jpeg_quality)  # file type is automatically determined by suffix
        self._preserve_front_cover_source(album, cover_file, new_filename)
        return True

    def _fix_rename_cover(self, album: Album, cover_file: str, new_filename: str):
        album_path = self.ctx.config.library / album.path
        if str.lower(cover_file) == str.lower(new_filename):
            # filenames differ only in case
            num = 0
            while (temp := (album_path / cover_file).with_suffix(f".{num}")) and temp.exists():
                num += 1
            self.ctx.console.print(f"Renaming {cover_file} to {temp.name}")
            rename(album_path / cover_file, temp)
            self.ctx.console.print(f"Renaming {temp.name} to {new_filename}")
            rename(temp, album_path / new_filename)
        else:
            self.ctx.console.print(f"Renaming {cover_file} to {new_filename}")
            rename(album_path / cover_file, album_path / new_filename)
        self._preserve_front_cover_source(album, cover_file, new_filename)
        return True

    def _preserve_front_cover_source(self, album: Album, old_filename: str, new_filename: str):
        old = next(file for file in album.picture_files if file.filename == old_filename)
        if old.cover_source:
            if not album.album_id:
                raise ValueError("updating cover source requires database and album_id")

            # preserve cover_source setting on the file, other metadata will be corrected on rescan
            picture_files = [
                PictureFile(new_filename, file.file_info, file.modify_timestamp, file.cover_source) if file.filename == old_filename else file
                for file in album.picture_files
            ]
            album.picture_files = picture_files
            update_picture_files(self.ctx.db, album.album_id, album.picture_files)

    def _matches(self, filename: str, case_sensitive: bool) -> bool:
        path = Path(filename)
        if self.suffix:
            target = f"{self.stem}{self.suffix}"
            return (case_sensitive and path.name == target) or (not case_sensitive and str.lower(path.name) == str.lower(target))
        return (case_sensitive and path.stem == self.stem) or (not case_sensitive and str.lower(path.stem) == str.lower(self.stem))
