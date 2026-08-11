from dataclasses import dataclass
from enum import Enum, auto
from typing import Final

from albums.types import OtherFile, PictureFile, Track

MAX_IMAGE_SIZE: Final = 128 * 1024 * 1024  # don't load and scan image files larger than this. 16 MB is the max for ID3v2 and FLAC tags.


@dataclass(frozen=True)
class TargetRescan:
    source: PictureFile | Track | OtherFile
    tags: bool
    images: bool
    streams: bool


class AlbumScanResult(Enum):
    NO_TRACKS = auto()
    NEW = auto()
    UPDATED = auto()
    UNCHANGED = auto()
    REMOVED = auto()
