from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Stream:
    length: float = 0.0
    bitrate: int = 0
    channels: int = 0
    codec: str = "unknown"
    sample_rate: int = 0

    def to_dict(self):
        return self.__dict__


@dataclass
class Track:
    filename: str
    tags: dict[str, list[str]] = field(default_factory=dict)
    file_size: int = 0
    modify_timestamp: int = 0
    stream: Stream | None = None

    @classmethod
    def from_path(cls, file: Path):
        stat = file.stat()
        return cls(file.name, None, stat.st_size, int(stat.st_mtime), None)

    def to_dict(self):
        return self.__dict__ | {"stream": self.stream.to_dict() if self.stream else {}}


@dataclass
class Album:
    path: str
    tracks: list[Track] = field(default_factory=list)
    collections: list[str] = field(default_factory=list)
    ignore_checks: list[str] = field(default_factory=list)
    album_id: int | None = None

    def to_dict(self):
        return self.__dict__ | {"tracks": [t.to_dict() for t in self.tracks] if self.tracks else []}
