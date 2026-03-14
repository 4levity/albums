import logging
from pathlib import Path
from typing import Callable, override

from mutagen._tags import PaddingInfo
from mutagen.id3 import ID3
from mutagen.mp3 import MP3

from ...config import ID3v1Policy
from ...picture.scan import PictureScanner
from ..base_id3 import AbstractId3Tagger

logger = logging.getLogger(__name__)


class Mp3Tagger(AbstractId3Tagger[MP3]):
    _file: MP3

    def __init__(self, path: Path, picture_scanner: PictureScanner, padding: Callable[[PaddingInfo], int], id3v1: ID3v1Policy):
        super().__init__(picture_scanner, padding, id3v1)
        self._file = MP3(path)
        self._picture_scanner = picture_scanner
        self._id3v1 = id3v1

    @override
    def _get_codec(self):
        return "MP3"

    @override
    def _get_file(self):
        return self._file

    @override
    def _ensure_id3(self) -> ID3:
        if not self._file.tags:  # pyright: ignore[reportUnknownMemberType]
            self._file.tags = ID3()
        return self._file.tags  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

    @override
    def _save(self):
        self._get_file().save(padding=self._padding, v1=self._id3v1)  # pyright: ignore[reportUnknownMemberType]
