"""Types shared by the library scanner: scan results and targeted rescan requests."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Final

from albums.entities import OtherFile, PictureFile, Track

MAX_IMAGE_SIZE: Final = 128 * 1024 * 1024  # don't load and scan image files larger than this


class FileAspect(Enum):
    """An aspect of a file that the scanner reads and stores, and that can be selectively re-read from disk."""

    FIELDS = auto()  # metadata fields (including legacy fields)
    IMAGES = auto()  # embedded pictures, or picture file data (dimensions, hash, etc.)
    STREAMS = auto()  # stream info (codec, sample rate, etc.) and whether the file contains video


ALL_FILE_ASPECTS: Final = frozenset(FileAspect)


@dataclass(frozen=True)
class TargetRescan:
    """A file from a previous scan, with the aspects that should be re-read from disk.

    Aspects not in :attr:`aspects` are kept from :attr:`source` (when the source entity type allows it,
    e.g. a ``PictureFile`` has no fields or streams to keep). See ``rescan.needs_rescan`` for how
    the set of aspects is determined.
    """

    source: PictureFile | Track | OtherFile
    aspects: frozenset[FileAspect]


class AlbumScanResult(Enum):
    """Outcome of scanning an album: no tracks, new, updated, unchanged, or removed (no more tracks on disk)."""

    NO_TRACKS = auto()
    NEW = auto()
    UPDATED = auto()
    UNCHANGED = auto()
    REMOVED = auto()
