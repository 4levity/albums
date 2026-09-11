"""Enumerate the folders in a directory tree, and the audio and image files in a folder along with minimal stat information."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Generator, List, Tuple

from albums.picture import SUPPORTED_IMAGE_SUFFIXES
from albums.tagger import AUDIO_FILE_SUFFIXES

SCAN_SUFFIXES: Final = frozenset(AUDIO_FILE_SUFFIXES | SUPPORTED_IMAGE_SUFFIXES)


@dataclass(frozen=True)
class MiniStat:
    """Small comparable subset of a file's stat: size and modify time (seconds)."""

    file_size: int
    modify_timestamp: int  # seconds


def walk_paths(root: Path) -> Generator[str, None, None]:
    """Yield ``root`` and every folder beneath it as relative paths with a trailing path separator.

    Symlinked folders are followed (matching the previous glob-based behavior); folder symlinks that
    form a cycle will loop forever.
    """
    yield "."
    stack: List[Tuple[str, str]] = [(str(root), "")]
    while stack:
        current, rel = stack.pop()
        try:
            entries = os.scandir(current)
        except OSError:
            continue  # skip unreadable folders
        with entries:
            for entry in entries:
                if entry.name.startswith("."):  # glob does not descend into hidden folders
                    continue
                try:
                    if not entry.is_dir():
                        continue
                except OSError:
                    continue
                new_rel = f"{rel}{entry.name}{os.sep}"
                yield new_rel
                stack.append((entry.path, new_rel))


def stat_dir(dir: Path) -> Generator[Tuple[Path, MiniStat], None, None]:
    """Yield (path, MiniStat) for each scannable file (audio or image) directly in the directory."""
    if not dir.is_dir():
        return
    with os.scandir(dir) as it:
        for entry in it:
            if entry.is_file() and str.lower(Path(entry.path).suffix) in SCAN_SUFFIXES:
                stat = entry.stat()
                yield (Path(entry.path), MiniStat(stat.st_size, int(stat.st_mtime)))
