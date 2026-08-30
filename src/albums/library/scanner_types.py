"""Types shared by the library scanner: scan results and targeted rescan requests."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Final

from albums.entities import OtherFile, PictureFile, Track

MAX_IMAGE_SIZE: Final = 128 * 1024 * 1024  # don't load and scan image files larger than this


@dataclass(frozen=True)
class TargetRescan:
    """A file from a previous scan, with flags indicating which parts (fields/images/streams) should be re-read."""

    source: PictureFile | Track | OtherFile
    fields: bool
    images: bool
    streams: bool


class AlbumScanResult(Enum):
    """Outcome of scanning an album: no tracks, new, updated, unchanged, or removed (no more tracks on disk)."""

    NO_TRACKS = auto()
    NEW = auto()
    UPDATED = auto()
    UNCHANGED = auto()
    REMOVED = auto()
