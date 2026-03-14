from pathlib import Path

from ..config import ID3v1Policy
from .folder import AlbumTagger


class AlbumTaggerProvider:
    _base_path: Path
    _tagger: AlbumTagger | None = None
    _id3v1: ID3v1Policy

    def __init__(self, base_path: Path, id3v1: ID3v1Policy):
        self._base_path = base_path
        self._id3v1 = id3v1

    def get(self, folder: str | Path) -> AlbumTagger:
        path = self._base_path / folder
        if not self._tagger or self._tagger.path() != path:
            self._tagger = AlbumTagger(path, id3v1=self._id3v1)
        return self._tagger
