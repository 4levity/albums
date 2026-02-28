import base64
from pathlib import Path
from typing import Callable, Generator, List, Tuple, override

from mutagen._tags import PaddingInfo
from mutagen.flac import Picture as FlacPicture
from mutagen.oggvorbis import OggVorbis

from ..picture.scan import PictureScanner
from .base_mutagen import AbstractMutagenTagger
from .helpers import album_picture_to_flac, scan_flac_picture, vorbis_comment_set_tag, vorbis_comment_tags
from .types import BasicTag, Picture


class OggVorbisTagger(AbstractMutagenTagger):
    _file: OggVorbis
    _picture_scanner: PictureScanner

    def __init__(self, path: Path, picture_scanner: PictureScanner, padding: Callable[[PaddingInfo], int]):
        super().__init__(padding)
        self._file = OggVorbis(path)
        self._picture_scanner = picture_scanner

    @override
    def get_pictures(self) -> Generator[Tuple[Picture, bytes], None, None]:
        yield from (scan_flac_picture(flac_picture, self._picture_scanner) for flac_picture in self._load_flac_pictures())

    @override
    def _add_picture(self, new_picture: Picture, image_data: bytes) -> None:
        flac_picture = album_picture_to_flac(new_picture, image_data)
        new_pictures = self._get_picture_blocks()
        new_pictures.append(base64.b64encode(flac_picture.write()).decode("ascii"))
        self._file.tags["metadata_block_picture"] = new_pictures  # pyright: ignore[reportOptionalSubscript]

    @override
    def _get_codec(self):
        return "Ogg Vorbis"

    @override
    def _get_file(self):
        return self._file

    @override
    def _remove_picture(self, remove_picture: Picture) -> None:
        new_picture_blocks = [
            base64_block
            for base64_block in self._get_picture_blocks()
            if scan_flac_picture(FlacPicture(base64.b64decode(base64_block)), self._picture_scanner)[0] != remove_picture
        ]
        self._file.tags["metadata_block_picture"] = new_picture_blocks  # pyright: ignore[reportOptionalSubscript]

    @override
    def _scan_tags(self):
        return vorbis_comment_tags(self._file.tags)  # pyright: ignore[reportArgumentType]

    @override
    def _set_tag(self, tag: BasicTag, value: str | List[str] | None):
        vorbis_comment_set_tag(self._file.tags, tag, value)  # pyright: ignore[reportArgumentType]

    def _get_picture_blocks(self) -> list[str]:
        return self._file.get("metadata_block_picture", [])  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportReturnType]

    def _load_flac_pictures(self) -> Generator[FlacPicture, None, None]:
        return (FlacPicture(base64.b64decode(base64_block)) for base64_block in self._get_picture_blocks())
