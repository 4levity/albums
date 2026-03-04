from contextlib import contextmanager
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Collection, Generator, List, Tuple

from mutagen._tags import PaddingInfo

from ..picture.format import SUPPORTED_IMAGE_SUFFIXES
from ..picture.scan import PictureScanner
from .flac import FlacTagger
from .image_file_reader import ImageFileReader
from .m4a import M4aTagger
from .mp3 import ID3v1Policy, Mp3Tagger
from .oggvorbis import OggVorbisTagger
from .types import BasicTag, TaggerFile
from .universal import UniversalTagger


class Cap(Enum):
    BASIC_TAGS = auto()
    FORMATTED_TRACK_NUMBER = auto()
    PICTURES = auto()
    PICTURE_TYPE = auto()


SUFFIX_SUPPORT = {
    ".flac": {Cap.BASIC_TAGS, Cap.FORMATTED_TRACK_NUMBER, Cap.PICTURES, Cap.PICTURE_TYPE},
    ".m4a": {Cap.BASIC_TAGS, Cap.PICTURES},
    ".mp3": {Cap.BASIC_TAGS, Cap.FORMATTED_TRACK_NUMBER, Cap.PICTURES, Cap.PICTURE_TYPE},
    ".ogg": {Cap.BASIC_TAGS, Cap.FORMATTED_TRACK_NUMBER, Cap.PICTURES, Cap.PICTURE_TYPE},
}
SUFFIX_SUPPORT.update((suffix, {Cap.PICTURES}) for suffix in SUPPORTED_IMAGE_SUFFIXES)


class AlbumTagger:
    @staticmethod
    def supports(filename: str, *needs: Cap) -> bool:
        if not needs:
            return False
        caps = SUFFIX_SUPPORT.get(Path(filename).suffix, set())
        return all(need in caps for need in needs)

    _folder: Path
    _padding: Callable[[PaddingInfo], int]
    _picture_scanner: PictureScanner
    _id3v1: ID3v1Policy

    def __init__(
        self,
        folder: Path,
        padding: Callable[[PaddingInfo], int] = lambda info: info.get_default_padding(),
        id3v1: ID3v1Policy = ID3v1Policy.UPDATE,
    ):
        self._folder = folder
        self._padding = padding
        self._picture_scanner = PictureScanner()
        self._id3v1 = id3v1

    @contextmanager
    def open(self, filename: str) -> Generator[TaggerFile, Any, None]:
        file = Path(filename)
        if str(file.parent) != ".":
            raise ValueError(f"parameter must be a filename only, this AlbumTagger only works in {str(self._folder)}")

        path = Path(self._folder / file)
        suffix = str.lower(path.suffix)
        tagger_file: TaggerFile | None = None
        try:
            if suffix == ".flac":
                tagger_file = FlacTagger(path, picture_scanner=self._picture_scanner, padding=self._padding)
            elif suffix == ".m4a":
                tagger_file = M4aTagger(path, picture_scanner=self._picture_scanner, padding=self._padding)
            elif suffix == ".mp3":
                tagger_file = Mp3Tagger(path, picture_scanner=self._picture_scanner, padding=self._padding, id3v1=self._id3v1)
            elif suffix == ".ogg":
                tagger_file = OggVorbisTagger(path, picture_scanner=self._picture_scanner, padding=self._padding)
            elif suffix in SUPPORTED_IMAGE_SUFFIXES:
                tagger_file = ImageFileReader(path, picture_scanner=self._picture_scanner)
            else:
                tagger_file = UniversalTagger(path, padding=self._padding)
            yield tagger_file
        finally:
            if tagger_file is not None:
                tagger_file.close()

    def get_picture_scanner(self) -> PictureScanner:
        return self._picture_scanner

    def path(self) -> Path:
        return self._folder

    def set_basic_tags(self, path: Path, tag_values: Collection[Tuple[BasicTag, str | List[str] | None]]):
        if path.parent != self._folder:
            raise ValueError(f"invalid path {str(path)} this AlbumTagger only works in {str(self._folder)}")
        with self.open(path.name) as f:
            for tag, value in tag_values:
                f.set_tag(tag, value)
