"""Enumerate the audio and image files in a folder along with minimal stat information."""

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Generator, Tuple

from albums.picture import SUPPORTED_IMAGE_SUFFIXES
from albums.tagger import AUDIO_FILE_SUFFIXES

SCAN_SUFFIXES: Final = frozenset(AUDIO_FILE_SUFFIXES | SUPPORTED_IMAGE_SUFFIXES)


@dataclass(frozen=True)
class MiniStat:
    """Small comparable subset of a file's stat: size and modify time (seconds)."""

    file_size: int
    modify_timestamp: int  # seconds


def stat_dir(dir: Path) -> Generator[Tuple[Path, MiniStat], None, None]:
    """Yield (path, MiniStat) for each scannable file (audio or image) directly in the directory."""
    for entry in dir.iterdir() if dir.is_dir() else ():
        if entry.is_file() and str.lower(entry.suffix) in SCAN_SUFFIXES:
            stat = entry.stat()
            yield (entry, MiniStat(stat.st_size, int(stat.st_mtime)))
