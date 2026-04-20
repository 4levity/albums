from dataclasses import dataclass
from pathlib import Path
from typing import Final, Generator, Tuple

from ..picture.format import SUPPORTED_IMAGE_SUFFIXES
from ..tagger.folder import AUDIO_FILE_SUFFIXES

SCAN_SUFFIXES: Final = frozenset(AUDIO_FILE_SUFFIXES | SUPPORTED_IMAGE_SUFFIXES)


@dataclass(frozen=True)
class MiniStat:
    file_size: int
    modify_timestamp: int  # seconds


def stat_dir(dir: Path) -> Generator[Tuple[Path, MiniStat], None, None]:
    for entry in dir.iterdir() if dir.is_dir() else ():
        if entry.is_file() and str.lower(entry.suffix) in SCAN_SUFFIXES:
            stat = entry.stat()
            yield (entry, MiniStat(stat.st_size, int(stat.st_mtime)))


def read_binary_file(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()
