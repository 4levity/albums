import base64
import logging
from dataclasses import dataclass, field
from enum import Enum, IntEnum, StrEnum, auto
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Tuple, Union

from rich.console import RenderableType

type CheckConfiguration = Dict[str, Union[str, int, float, bool, List[str]]]

logger = logging.getLogger(__name__)


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

    @staticmethod
    def from_filename(filename: str):
        if any(match in str.lower(filename) for match in ["folder", ".folder", "cover", "album", "front", "thumbnail"]):
            return PictureType.COVER_FRONT
        return PictureType.OTHER


@dataclass
class Picture:
    picture_type: PictureType
    format: str
    width: int
    height: int
    file_size: int
    file_hash: bytes  # 32 bit xxhash
    description: str = ""

    # fields below are not part of equality/identity of the image

    load_issue: dict[str, str | int] | None = None  # load-time issues report is NOT part of equality, only real image data
    modify_timestamp: int | None = None  # timestamp is NOT part of equality and is only present if the picture is not embedded
    embed_ix: int = 0  # the index of this image (the first image loaded from a file is 0, etc) also NOT part of equality
    cover_source: bool = False  # if this file is the high-resolution source for embedded front cover art (picture_type must be FRONT_COVER)

    def to_dict(self):
        result = dict(self.__dict__)
        result["file_hash"] = base64.b64encode(self.file_hash).decode()
        if self.load_issue is None:
            del result["load_issue"]
        if self.modify_timestamp is None:
            del result["modify_timestamp"]
        if not self.cover_source:
            del result["cover_source"]
        return result

    # Keep modify_timestamp and load info with this object, but also deduplicate images easily (ignoring those two fields)
    def __eq__(self, other: Any):
        if not isinstance(other, Picture):
            return NotImplemented
        return self._comparable() == other._comparable()

    def __hash__(self):
        return hash(self._comparable())

    def _comparable(self):
        return frozenset((k, v) for k, v in self.__dict__.items() if k not in {"load_issue", "modify_timestamp", "embed_ix", "cover_source"})


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
    scanner: int = 0

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


class ProblemCategory(Enum):
    TAGS = auto()  # issues with tags (except for picture tags)
    PICTURES = auto()  # issues with album art
    FILENAMES = auto()  # track filenames
    FOLDERS = auto()  # organization, folder names
    OTHER = auto()  # general problems with the album


@dataclass
class Fixer:
    fix: Callable[[str], bool]
    options: list[str]  # at least one option should be provided if "free text" is not an option
    option_free_text: bool = False
    option_automatic_index: int | None = None
    # TODO these Lists should be Sequences?
    table: Tuple[List[str], List[List[RenderableType]] | Callable[[], List[List[RenderableType]]]] | None = None  # tuple (headers, rows/rows())
    prompt: str = "select an option"  # e.g. "select an album artist for all tracks"

    def get_table(self) -> Tuple[List[str], List[List[RenderableType]]] | None:
        if self.table is None:
            return None
        (headers, get_rows) = self.table
        rows: List[List[RenderableType]] = get_rows if isinstance(get_rows, List) else get_rows()  # pyright: ignore[reportUnknownVariableType]
        return (headers, rows)


@dataclass(frozen=True)
class CheckResult:
    category: ProblemCategory
    message: str
    fixer: Fixer | None = None


class RescanOption(StrEnum):
    ALWAYS = auto()
    NEVER = auto()
    AUTO = auto()


class PathCompatiblityOption(StrEnum):
    LINUX = "Linux"
    WINDOWS = "Windows"
    MACOS = "macOS"
    POSIX = "POSIX"
    UNIVERSAL = "universal"


def default_checks_config() -> dict[str, CheckConfiguration]:
    from .checks.all import ALL_CHECKS  # local import because .checks.all imports all checks which will import this module

    return dict((check.name, check.default_config.copy()) for check in ALL_CHECKS)


@dataclass
class Configuration:
    checks: Dict[str, CheckConfiguration] = field(default_factory=default_checks_config)
    library: Path = Path(".")
    rescan: RescanOption = RescanOption.AUTO
    tagger: str = ""
    open_folder_command: str = ""
    path_compatibility: PathCompatiblityOption = PathCompatiblityOption.UNIVERSAL

    def to_values(self) -> Dict[str, Union[str, int, float, bool, List[str]]]:
        values: Dict[str, Union[str, int, float, bool, List[str]]] = {
            "settings.library": str(self.library),
            "settings.rescan": str(self.rescan),
            "settings.tagger": self.tagger,
            "settings.open_folder_command": self.open_folder_command,
            "settings.path_compatibility": self.path_compatibility,
        }
        defaults = default_checks_config()
        for check_name, check_config in self.checks.items():
            for name, value in check_config.items():
                if check_name not in defaults or name not in defaults[check_name]:
                    raise ValueError(f"can't save unknown check configuration {check_name}.{name}")
                if type(value) is not type(defaults[check_name][name]):
                    raise ValueError(
                        f"can't save {check_name}.{name} because wrong data type {type(value)} (expected {type(defaults[check_name][name])})"
                    )
                values[f"{check_name}.{name}"] = value
        return values

    @classmethod
    def from_values(cls, values: Iterator[Tuple[str, Union[str, int, float, bool, List[str]]]]):
        config = Configuration()
        ignored_values = False
        for k, value in values:
            tokens = k.split(".")
            if len(tokens) != 2:
                logger.warning(f"ignoring invalid configuration key {k} (expected section.name)")
                ignored_values = True
                continue
            [section, name] = tokens
            if section == "settings":
                if name == "library":
                    config.library = Path(str(value))
                elif name == "rescan":
                    config.rescan = RescanOption(value)
                elif name == "tagger":
                    config.tagger = str(value)
                elif name == "open_folder_command":
                    config.open_folder_command = str(value)
                elif name == "path_compatibility":
                    config.path_compatibility = PathCompatiblityOption(value)
                else:
                    logger.warning(f"ignoring unknown configuration item {k} = {str(value)}")
                    ignored_values = True
            else:
                if section not in config.checks or name not in config.checks[section]:
                    logger.warning(f"ignoring unknown configuration item {k} = {str(value)}")
                    ignored_values = True
                elif type(value) is not type(config.checks[section][name]):
                    logger.warning(f"ignoring configuration item {k} with wrong type {type(value)} (expected {type(config.checks[section][name])})")
                    ignored_values = True
                else:
                    config.checks[section][name] = value
        return (config, ignored_values)
