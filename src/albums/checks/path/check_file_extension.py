import logging
from itertools import chain
from os import rename
from pathlib import Path
from typing import Final, Sequence, Tuple, override

from rich.markup import escape

from ...tagger.folder import AUDIO_FILE_SUFFIXES
from ...types import Album, CheckConfiguration, CheckResult, Fixer, FixResult
from ...words.make import pluralize
from ..base_check import Check

logger: Final = logging.getLogger(__name__)


class CheckFileExtension(Check):
    name = "file-extension"
    default_config = {"enabled": True, "lowercase_all": False}
    must_pass_checks = {"illegal-pathname"}

    @override
    def init(self, check_config: CheckConfiguration):
        self.lowercase_all = bool(check_config.get("lowercase_all", self.default_config["lowercase_all"]))

    def check(self, album: Album):
        check_file_list = (
            chain(album.tracks, album.picture_files, album.other_files)
            if self.lowercase_all
            else chain(album.tracks, (o for o in album.other_files if Path(o.filename).suffix.lower() in AUDIO_FILE_SUFFIXES))
        )
        files = sorted(
            ((file.filename, str(Path(file.filename).with_suffix(Path(file.filename).suffix.lower()))) for file in check_file_list),
            key=lambda item: item[0],
        )
        rename_files = [(old, new) for old, new in files if old != new]
        if len(rename_files) == 0:
            return None
        message = f'bad file {pluralize("extension", rename_files)}, example "{rename_files[0][0]}" should be "{rename_files[0][1]}"'

        final_names = [new for _, new in files]
        if len(final_names) != len(set(final_names)):
            return CheckResult(message + " (automatic fix not possible due to filename conflict)")

        table = (
            ["filename", "proposed new extension"],
            [[escape(filename), suffix.lower() if suffix.lower() != suffix else ""] for filename, suffix in files],
        )
        options = [">> Change file extensions"]
        option_automatic_index = 0
        return CheckResult(
            message,
            Fixer(lambda _: self._fix_rename(album, rename_files), options, False, option_automatic_index, table),
        )

    def _fix_rename(self, album: Album, rename_files: Sequence[Tuple[str, str]]):
        album_path = self.ctx.config.library / album.path
        rename_files_2: Sequence[Tuple[str, str]] = []

        # rename in two passes, in case OS/filesystem doesn't accept case-only rename
        for old_filename, new_filename in rename_files:
            num = 0
            while (temp := (album_path / old_filename).with_suffix(f".{num}")) and temp.exists():
                num += 1
            self.ctx.console.print(f"Temporarily renaming {escape(old_filename)} to {escape(temp.name)}", highlight=False)
            rename(album_path / old_filename, album_path / temp.name)
            rename_files_2.append((temp.name, new_filename))

        for old_filename, new_filename in rename_files_2:
            self.ctx.console.print(f"Renaming {escape(old_filename)} to {escape(str(new_filename))}", highlight=False)
            rename(album_path / old_filename, album_path / new_filename)
        return FixResult.CHANGED_ALBUM
