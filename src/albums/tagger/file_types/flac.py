"""FLAC file tagging via mutagen, using Vorbis comments and embedded pictures."""

from copy import copy
from pathlib import Path
from typing import Callable, Generator, List, Tuple, override

from mutagen._tags import PaddingInfo
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture

from ...picture.scan import PictureScanner
from ..base_mutagen import AbstractMutagenTagger
from ..helpers import album_picture_to_flac, scan_flac_picture
from ..types import BasicField, Picture
from ..vorbis import vorbis_comment_fields, vorbis_comment_legacy_fields, vorbis_comment_set_field


class FlacTagger(AbstractMutagenTagger[FLAC]):
    """Tagger for FLAC files (Vorbis comments and FLAC pictures)."""

    _file: FLAC
    _picture_scanner: PictureScanner

    def __init__(self, path: Path, picture_scanner: PictureScanner, padding: Callable[[PaddingInfo], int]):
        super().__init__(padding)
        self._file = FLAC(path)
        self._picture_scanner = picture_scanner

    @override
    def get_pictures(self) -> Generator[Tuple[Picture, bytes], None, None]:
        flac_pics: list[FlacPicture] = self._file.pictures  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        for pic in flac_pics:
            yield scan_flac_picture(pic, self._picture_scanner)

    @override
    def _add_picture(self, new_picture: Picture, image_data: bytes) -> None:
        flac_picture = album_picture_to_flac(new_picture, image_data)
        self._file.add_picture(flac_picture)  # pyright: ignore[reportUnknownMemberType]

    @override
    def _get_codec(self):
        return "FLAC"

    @override
    def _get_file(self):
        return self._file

    @override
    def _remove_picture(self, remove_picture: Picture) -> None:
        pictures: list[tuple[Picture, bytes]] = [(copy(pic), image_data) for pic, image_data in self.get_pictures() if pic != remove_picture]
        self._file.clear_pictures()
        for pic, data in pictures:
            self._add_picture(pic, data)

    @override
    def get_fields(self):
        return vorbis_comment_fields(self._file.tags)  # pyright: ignore[reportArgumentType]

    @override
    def get_legacy_fields(self):
        return vorbis_comment_legacy_fields(self._file.tags)  # pyright: ignore[reportUnknownMemberType, reportArgumentType]

    @override
    def _set_field(self, field: BasicField | str, value: str | List[str] | None):
        vorbis_comment_set_field(self._file.tags, field, value)  # pyright: ignore[reportArgumentType]
