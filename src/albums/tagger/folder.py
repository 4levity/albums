from contextlib import contextmanager
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Collection, Final, Generator, List, Mapping, Set, Tuple

from mutagen._tags import PaddingInfo

from ..config import ID3v1Policy
from ..picture.format import SUPPORTED_IMAGE_SUFFIXES
from ..picture.scan import PictureScanner, PictureScannerCache
from .file_types.aiff import AiffTagger
from .file_types.asf import AsfTagger
from .file_types.flac import FlacTagger
from .file_types.image_file_reader import ImageFileReader
from .file_types.mp3 import Mp3Tagger
from .file_types.mp4 import Mp4Tagger
from .file_types.oggvorbis import OggVorbisTagger
from .file_types.universal import UniversalTagger
from .types import BasicTag, TaggerFile
from .unreadable import UnreadableTagger


class Cap(Enum):
    BASIC_TAGS = auto()
    FORMATTED_TRACK_NUMBER = auto()
    PICTURES = auto()
    PICTURE_TYPE = auto()
    VORBIS_COMMENT = auto()


_SUFFIX_SUPPORT = {
    ".flac": {Cap.BASIC_TAGS, Cap.FORMATTED_TRACK_NUMBER, Cap.PICTURES, Cap.PICTURE_TYPE, Cap.VORBIS_COMMENT},
    ".m4a": {Cap.BASIC_TAGS, Cap.PICTURES},
    ".m4b": {Cap.BASIC_TAGS, Cap.PICTURES},
    ".mp4": {Cap.BASIC_TAGS, Cap.PICTURES},
    ".mp3": {Cap.BASIC_TAGS, Cap.FORMATTED_TRACK_NUMBER, Cap.PICTURES, Cap.PICTURE_TYPE},
    ".ogg": {Cap.BASIC_TAGS, Cap.FORMATTED_TRACK_NUMBER, Cap.PICTURES, Cap.PICTURE_TYPE, Cap.VORBIS_COMMENT},
    ".wma": {Cap.BASIC_TAGS, Cap.FORMATTED_TRACK_NUMBER},  # ASF / WMA reading pictures is implemented but so far untested (so no writing)
    ".asf": {Cap.BASIC_TAGS, Cap.FORMATTED_TRACK_NUMBER},
    ".aif": {Cap.BASIC_TAGS, Cap.FORMATTED_TRACK_NUMBER, Cap.PICTURES, Cap.PICTURE_TYPE},
    ".aiff": {Cap.BASIC_TAGS, Cap.FORMATTED_TRACK_NUMBER, Cap.PICTURES, Cap.PICTURE_TYPE},
}
AUDIO_FILE_SUFFIXES: Final = frozenset(_SUFFIX_SUPPORT.keys())

_SUFFIX_SUPPORT.update((suffix, {Cap.PICTURES}) for suffix in SUPPORTED_IMAGE_SUFFIXES)
SUFFIX_SUPPORT: Final[Mapping[str, Set[Cap]]] = _SUFFIX_SUPPORT


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
        preload: PictureScannerCache = {},
    ):
        self._folder = folder
        self._padding = padding
        self._picture_scanner = PictureScanner(preload)
        self._id3v1 = id3v1

    @contextmanager
    def open(self, filename: str) -> Generator[TaggerFile, Any, None]:
        file = Path(filename)
        if str(file.parent) != ".":
            raise ValueError(f"parameter must be a filename only, this AlbumTagger only works in {str(self._folder)}")

        tagger_file: TaggerFile | None = None
        try:
            tagger_file = self._get_tagger_file(Path(self._folder / file))
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

    def _get_tagger_file(self, path: Path):
        suffix = str.lower(path.suffix)
        try:
            if suffix == ".flac":
                tagger_file = FlacTagger(path, picture_scanner=self._picture_scanner, padding=self._padding)
            elif suffix in {".m4a", ".m4b", ".mp4"}:
                tagger_file = Mp4Tagger(path, picture_scanner=self._picture_scanner, padding=self._padding)
            elif suffix == ".mp3":
                tagger_file = Mp3Tagger(path, picture_scanner=self._picture_scanner, padding=self._padding, id3v1=self._id3v1)
            elif suffix == ".ogg":
                tagger_file = OggVorbisTagger(path, picture_scanner=self._picture_scanner, padding=self._padding)
            elif suffix in {".wma", ".asf"}:
                tagger_file = AsfTagger(path, picture_scanner=self._picture_scanner, padding=self._padding)
            elif suffix in {".aiff", ".aif"}:
                tagger_file = AiffTagger(path, picture_scanner=self._picture_scanner, padding=self._padding, id3v1=self._id3v1)
            elif suffix in SUPPORTED_IMAGE_SUFFIXES:
                tagger_file = ImageFileReader(path, picture_scanner=self._picture_scanner)
            else:
                tagger_file = UniversalTagger(path, padding=self._padding)
        except Exception as ex:
            tagger_file = UnreadableTagger(path.name, repr(ex))
        return tagger_file
