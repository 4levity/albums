import base64
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any


@dataclass
class Stream:
    length: float = 0.0
    bitrate: int = 0
    channels: int = 0
    codec: str = "unknown"
    sample_rate: int = 0

    def to_dict(self):
        return self.__dict__


class PictureType(IntEnum):
    """
    ID3 picture type, also used with other tag systems
    """

    OTHER = 0
    FILE_ICON = 1
    OTHER_FILE_ICON = 2
    COVER_FRONT = 3
    COVER_BACK = 4
    LEAFLET_PAGE = 5
    MEDIA = 6
    LEAD_ARTIST = 7
    ARTIST = 8
    CONDUCTOR = 9
    BAND = 10
    COMPOSER = 11
    LYRICIST = 12
    RECORDING_LOCATION = 13
    DURING_RECORDING = 14
    DURING_PERFORMANCE = 15
    SCREEN_CAPTURE = 16
    FISH = 17
    ILLUSTRATION = 18
    BAND_LOGOTYPE = 19
    PUBLISHER_LOGOTYPE = 20


@dataclass
class Picture:
    picture_type: PictureType
    format: str
    width: int
    height: int
    file_size: int
    file_hash: bytes  # 32 bit xxhash
    mismatch: dict[str, str | int] | None = None  # load-time metadata mismatch report is NOT part of equality, only real image data
    modify_timestamp: int | None = None  # timestamp is NOT part of equality and is only present if the picture is not embedded

    def to_dict(self):
        return self.__dict__ | {"file_hash": base64.b64encode(self.file_hash).decode()}

    # Keep modify_timestamp and mismatch info with this object, but also deduplicate images easily (ignoring those two fields)
    def __eq__(self, other: Any):
        if not isinstance(other, Picture):
            return NotImplemented
        return self._comparable() == other._comparable()

    def __hash__(self):
        return hash(self._comparable())

    def _comparable(self):
        return frozenset((k, v) for k, v in self.__dict__.items() if k not in {"mismatch", "modify_timestamp"})


@dataclass
class Track:
    filename: str
    tags: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    file_size: int = 0
    modify_timestamp: int = 0
    stream: Stream | None = None
    pictures: list[Picture] = field(default_factory=list[Picture])

    @classmethod
    def from_path(cls, file: Path):
        stat = file.stat()
        return cls(file.name, {}, stat.st_size, int(stat.st_mtime), None)

    def to_dict(self):
        pictures = [picture.to_dict() for picture in self.pictures]
        return self.__dict__ | {"stream": self.stream.to_dict() if self.stream else {}} | {"pictures": pictures}


@dataclass
class Album:
    path: str
    tracks: list[Track] = field(default_factory=list[Track])
    collections: list[str] = field(default_factory=list[str])
    ignore_checks: list[str] = field(default_factory=list[str])
    picture_files: dict[str, Picture] = field(default_factory=dict[str, Picture])
    album_id: int | None = None

    def to_dict(self):
        pictures = dict((filename, picture.to_dict()) for (filename, picture) in self.picture_files.items())
        return self.__dict__ | {"tracks": [t.to_dict() for t in self.tracks] if self.tracks else []} | {"picture_files": pictures}

    def codec(self):
        codecs = {track.stream.codec if track.stream else "unknown" for track in self.tracks}
        return codecs.pop() if len(codecs) == 1 else "multiple"


@dataclass
class ScanHistoryEntry:
    timestamp: int
    folders_scanned: int
    albums_total: int
