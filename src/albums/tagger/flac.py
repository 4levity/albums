from copy import copy
from pathlib import Path
from typing import Callable, Generator, List, Tuple, override

from mutagen._tags import PaddingInfo
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture

from .base_mutagen import AbstractMutagenTagger
from .helpers import album_picture_to_flac, scan_flac_picture, vorbis_comment_set_tag, vorbis_comment_tags
from .picture import PictureScanner
from .types import AlbumPicture, BasicTag


class FlacTagger(AbstractMutagenTagger):
    _file: FLAC
    _picture_scanner: PictureScanner

    def __init__(self, path: Path, picture_scanner: PictureScanner, padding: Callable[[PaddingInfo], int]):
        super().__init__(padding)
        self._file = FLAC(path)
        self._padding = padding
        self._picture_scanner = picture_scanner

    @override
    def set_tag(self, tag: BasicTag, value: str | List[str] | None):
        vorbis_comment_set_tag(self._file.tags, tag, value)  # pyright: ignore[reportArgumentType]

    @override
    def get_pictures(self) -> Generator[Tuple[AlbumPicture, bytes], None, None]:
        flac_pics: list[FlacPicture] = self._file.pictures  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        for pic in flac_pics:
            yield scan_flac_picture(pic, self._picture_scanner)

    @override
    def add_picture(self, new_picture: AlbumPicture, image_data: bytes) -> None:
        flac_picture = album_picture_to_flac(new_picture, image_data)
        self._file.add_picture(flac_picture)  # pyright: ignore[reportUnknownMemberType]

    @override
    def remove_picture(self, remove_picture: AlbumPicture) -> None:
        pictures: list[tuple[AlbumPicture, bytes]] = [(copy(pic), image_data) for pic, image_data in self.get_pictures() if pic != remove_picture]
        self._file.clear_pictures()
        for pic, data in pictures:
            self.add_picture(pic, data)

    @override
    def _get_file(self):
        return self._file

    @override
    def _get_codec(self):
        return "FLAC"

    @override
    def _scan_tags(self):
        return vorbis_comment_tags(self._file.tags)  # pyright: ignore[reportArgumentType]
