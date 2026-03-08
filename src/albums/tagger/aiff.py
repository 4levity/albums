import logging
from pathlib import Path
from typing import Callable, override

from mutagen._tags import PaddingInfo
from mutagen.aiff import AIFF
from mutagen.id3 import ID3

from ..picture.scan import PictureScanner
from .id3 import AbstractId3Tagger, ID3v1Policy

logger = logging.getLogger(__name__)


class AiffTagger(AbstractId3Tagger[AIFF]):
    _file: AIFF

    def __init__(self, path: Path, picture_scanner: PictureScanner, padding: Callable[[PaddingInfo], int], id3v1: ID3v1Policy):
        super().__init__(picture_scanner, padding, id3v1)
        self._file = AIFF(path)
        self._picture_scanner = picture_scanner
        self._id3v1 = id3v1

    @override
    def _get_file(self):
        return self._file

    @override
    def _get_codec(self):
        return "AIFF"

    @override
    def _ensure_id3(self) -> ID3:
        if not self._file.tags:  # pyright: ignore[reportUnknownMemberType]
            self._file.add_tags()
        return self._file.tags  # pyright: ignore[reportReturnType]

    @override
    def _save(self):
        self._get_file().save(padding=self._padding)  # pyright: ignore[reportUnknownMemberType]
