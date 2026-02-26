from pathlib import Path

from .folder import AlbumTagger


class AlbumTaggerProvider:
    _base_path: Path
    _tagger: AlbumTagger | None = None

    def __init__(self, base_path: Path):
        self._base_path = base_path

    def get(self, folder: str | Path) -> AlbumTagger:
        path = self._base_path / folder
        if not self._tagger or self._tagger.path() != path:
            self._tagger = AlbumTagger(path)
        return self._tagger
