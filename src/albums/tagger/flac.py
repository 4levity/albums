from copy import copy
from pathlib import Path
from typing import Callable, List, Tuple, override

from mutagen._tags import PaddingInfo
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture

from .base_mutagen import AbstractMutagenTagger
from .helpers import album_picture_to_flac, scan_flac_picture, vorbis_comment_set_tag, vorbis_comment_tags
from .picture import PictureScanner
from .types import AlbumPicture, BasicTag, PictureType


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
    def get_image_data(self, picture_type: PictureType, embed_ix: int) -> bytes:
        flac_pictures: list[FlacPicture] = self._file.pictures  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        if len(flac_pictures) <= embed_ix:
            raise ValueError(f"cannot read image#{embed_ix} from {self._file.filename} ({len(flac_pictures)} pics)")
        pic = flac_pictures[embed_ix]
        if pic.type != picture_type.value:
            raise ValueError(
                f"unexpected image #{embed_ix} in {self._file.filename} expected type {picture_type.name} {picture_type.value} but was {pic.type}"
            )
        return pic.data  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

    @override
    def add_picture(self, new_picture: AlbumPicture, image_data: bytes, image_mode: str | None = None) -> None:
        flac_picture = album_picture_to_flac(new_picture, image_data, image_mode)
        self._file.add_picture(flac_picture)  # pyright: ignore[reportUnknownMemberType]

    @override
    def remove_picture(self, remove_picture: AlbumPicture) -> None:
        pictures: list[FlacPicture] = [copy(pic) for pic in self._file.pictures if pic != remove_picture]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType, reportUnknownMemberType]
        self._file.clear_pictures()
        for pic in pictures:
            self._file.add_picture(pic)  # pyright: ignore[reportUnknownMemberType]

    @override
    def _get_file(self):
        return self._file

    @override
    def _get_codec(self):
        return "FLAC"

    @override
    def _scan_tags(self):
        return vorbis_comment_tags(self._file.tags)  # pyright: ignore[reportArgumentType]

    @override
    def _scan_pictures(self) -> Tuple[AlbumPicture, ...]:
        flac_pics: list[FlacPicture] = self._file.pictures  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        return tuple(scan_flac_picture(pic, self._picture_scanner) for pic in flac_pics)
