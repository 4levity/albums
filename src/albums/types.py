from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Collection, Dict, Mapping, Sequence, Tuple, Union

from rich.console import RenderableType

from .picture.info import PictureInfo
from .tagger.types import BasicTag, Picture, PictureType, StreamInfo

type CheckConfiguration = Dict[str, Union[str, int, float, bool, Sequence[str]]]


@dataclass
class Track:
    filename: str
    tags: Mapping[BasicTag, Sequence[str]] = field(default_factory=dict[BasicTag, Sequence[str]])
    file_size: int = 0
    modify_timestamp: int = 0
    stream: StreamInfo | None = None
    pictures: Sequence[Picture] = field(default_factory=list[Picture])

    @classmethod
    def from_path(cls, file: Path):
        stat = file.stat()
        return cls(file.name, {}, stat.st_size, int(stat.st_mtime), None)

    def to_dict(self):
        pictures = [picture.to_dict() for picture in self.pictures]
        return self.__dict__ | {"stream": self.stream.to_dict() if self.stream else {}} | {"pictures": pictures}


@dataclass(frozen=True)
class PictureFile:
    filename: str
    file_info: PictureInfo
    modify_timestamp: int
    cover_source: bool

    def to_dict(self):
        return self.__dict__ | {"file_info": self.file_info.to_dict()}

    def to_picture(self) -> Picture:
        return Picture(self.file_info, PictureType.from_filename(self.filename), "")


@dataclass
class Album:
    path: str
    tracks: Sequence[Track] = field(default_factory=list[Track])
    collections: Collection[str] = field(default_factory=list[str])
    ignore_checks: Collection[str] = field(default_factory=list[str])
    picture_files: Sequence[PictureFile] = field(default_factory=list[PictureFile])
    album_id: int | None = None
    scanner: int = 0

    def to_dict(self):
        pictures = [picture.to_dict() for picture in self.picture_files]
        return self.__dict__ | {"tracks": [track.to_dict() for track in self.tracks]} | {"picture_files": pictures}

    def codec(self):
        codecs = {track.stream.codec if track.stream else "unknown" for track in self.tracks}
        return codecs.pop() if len(codecs) == 1 else "multiple"


@dataclass
class ScanHistoryEntry:
    timestamp: int
    folders_scanned: int
    albums_total: int


@dataclass
class Fixer:
    fix: Callable[[str], bool]
    options: Sequence[str]  # at least one option should be provided if "free text" is not an option
    option_free_text: bool = False
    option_automatic_index: int | None = None
    table: Tuple[Sequence[str], Sequence[Sequence[RenderableType]] | Callable[[], Sequence[Sequence[RenderableType]]]] | None = None
    prompt: str = "select an option"  # e.g. "select an album artist for all tracks"

    def get_table(self) -> Tuple[Sequence[str], Sequence[Sequence[RenderableType]]] | None:
        if self.table is None:
            return None
        (headers, get_rows) = self.table
        rows: Sequence[Sequence[RenderableType]] = get_rows if isinstance(get_rows, Sequence) else get_rows()  # pyright: ignore[reportUnknownVariableType]
        return (headers, rows)


@dataclass(frozen=True)
class CheckResult:
    message: str
    fixer: Fixer | None = None
