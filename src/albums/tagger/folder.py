from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Collection, Generator, List, Tuple

from mutagen._tags import PaddingInfo

from .flac import FlacTagger
from .mp3 import MP3Tagger
from .oggvorbis import OggVorbisTagger
from .picture import PictureScanner
from .types import BasicTag, TaggerFile
from .universal import UniversalTagger


class AlbumTagger:
    _folder: Path
    _padding: Callable[[PaddingInfo], int]
    _picture_scanner: PictureScanner

    def __init__(
        self,
        folder: Path,
        padding: Callable[[PaddingInfo], int] = lambda info: info.get_default_padding(),
    ):
        self._folder = folder
        self._padding = padding
        self._picture_scanner = PictureScanner()

    @contextmanager
    def open(self, filename: str) -> Generator[TaggerFile, Any, None]:
        file = Path(filename)
        if str(file.parent) != ".":
            raise ValueError(f"parameter must be a filename only, this AlbumTagger only works in {str(self._folder)}")
        tagger_file = self._get_file(Path(self._folder / file))
        try:
            yield tagger_file
        finally:
            tagger_file.save()

    def get_picture_scanner(self) -> PictureScanner:
        return self._picture_scanner

    def _get_file(self, path: Path) -> TaggerFile:
        suffix = str.lower(path.suffix)
        if suffix == ".flac":
            return FlacTagger(path, picture_scanner=self._picture_scanner, padding=self._padding)
        if suffix == ".mp3":
            return MP3Tagger(path, picture_scanner=self._picture_scanner, padding=self._padding)
        if suffix == ".ogg":
            return OggVorbisTagger(path, picture_scanner=self._picture_scanner, padding=self._padding)
        return UniversalTagger(path, padding=self._padding)

    def set_basic_tags(self, path: Path, tag_values: Collection[Tuple[str, str | List[str] | None]]):
        if path.parent != self._folder:
            raise ValueError(f"invalid path {str(path)} this AlbumTagger only works in {str(self._folder)}")
        with self.open(path.name) as f:
            for name, value in tag_values:
                f.set_tag(BasicTag(name), value)
