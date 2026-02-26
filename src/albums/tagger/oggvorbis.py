import base64
from pathlib import Path
from typing import Callable, Generator, List, Tuple, override

from mutagen._tags import PaddingInfo
from mutagen.flac import Picture as FlacPicture
from mutagen.oggvorbis import OggVorbis

from .base_mutagen import AbstractMutagenTagger
from .helpers import album_picture_to_flac, scan_flac_picture, vorbis_comment_set_tag, vorbis_comment_tags
from .picture import PictureScanner
from .types import AlbumPicture, BasicTag, PictureType


class OggVorbisTagger(AbstractMutagenTagger):
    _file: OggVorbis
    _picture_scanner: PictureScanner

    def __init__(self, path: Path, picture_scanner: PictureScanner, padding: Callable[[PaddingInfo], int]):
        super().__init__(padding)
        self._file = OggVorbis(path)
        self._picture_scanner = picture_scanner

    @override
    def set_tag(self, tag: BasicTag, value: str | List[str] | None):
        vorbis_comment_set_tag(self._file.tags, tag, value)  # pyright: ignore[reportArgumentType]

    @override
    def get_image_data(self, picture_type: PictureType, embed_ix: int) -> bytes:
        picture_blocks = self._get_picture_blocks()
        if len(picture_blocks) <= embed_ix:
            raise ValueError(f"cannot read image#{embed_ix} from {self._file.filename} ({len(picture_blocks)} pics)")
        flac_picture = FlacPicture(base64.b64decode(picture_blocks[embed_ix]))
        if flac_picture.type != picture_type.value:
            raise ValueError(f"unexpected image #{embed_ix} in {self._file.filename} expected type {picture_type.value} but was {flac_picture.type}")
        return flac_picture.data  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

    @override
    def add_picture(self, new_picture: AlbumPicture, image_data: bytes, image_mode: str | None = None) -> None:
        flac_picture = album_picture_to_flac(new_picture, image_data, image_mode)
        new_pictures = self._get_picture_blocks()
        new_pictures.append(base64.b64encode(flac_picture.write()).decode("ascii"))
        self._file.tags["metadata_block_picture"] = new_pictures  # pyright: ignore[reportOptionalSubscript]

    @override
    def remove_picture(self, remove_picture: AlbumPicture) -> None:
        self._file.tags["metadata_block_picture"] = [  # pyright: ignore[reportOptionalSubscript]
            base64_block
            for base64_block in self._get_picture_blocks()
            if scan_flac_picture(FlacPicture(base64.b64decode(base64_block)), self._picture_scanner) != remove_picture
        ]

    @override
    def _get_file(self):
        return self._file

    @override
    def _get_codec(self):
        return "Ogg Vorbis"

    @override
    def _scan_tags(self):
        return vorbis_comment_tags(self._file.tags)  # pyright: ignore[reportArgumentType]

    @override
    def _scan_pictures(self) -> Tuple[AlbumPicture, ...]:
        return tuple(scan_flac_picture(flac_picture, self._picture_scanner) for flac_picture in self._load_flac_pictures())

    def _load_flac_pictures(self) -> Generator[FlacPicture, None, None]:
        return (FlacPicture(base64.b64decode(base64_block)) for base64_block in self._get_picture_blocks())

    def _get_picture_blocks(self) -> list[str]:
        return self._file.get("metadata_block_picture", [])  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportReturnType]
