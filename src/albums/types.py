import logging
from dataclasses import dataclass, field
from enum import StrEnum, auto
from pathlib import Path
from typing import Callable, Collection, Dict, Iterator, Mapping, Sequence, Tuple, Union

from rich.console import RenderableType

from .tagger.types import BasicTag, Picture, StreamInfo

type CheckConfiguration = Dict[str, Union[str, int, float, bool, Sequence[str]]]

logger = logging.getLogger(__name__)


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


@dataclass
class PictureFile:
    picture: Picture
    modify_timestamp: int
    cover_source: bool

    def to_dict(self):
        return self.__dict__ | {"picture": self.picture.to_dict()}


@dataclass
class Album:
    path: str
    tracks: Sequence[Track] = field(default_factory=list[Track])
    collections: Collection[str] = field(default_factory=list[str])
    ignore_checks: Collection[str] = field(default_factory=list[str])
    picture_files: Mapping[str, PictureFile] = field(default_factory=dict[str, PictureFile])
    album_id: int | None = None
    scanner: int = 0

    def to_dict(self):
        pictures = dict((filename, picture.to_dict()) for (filename, picture) in self.picture_files.items())
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


class RescanOption(StrEnum):
    ALWAYS = auto()
    NEVER = auto()
    AUTO = auto()


class PathCompatibilityOption(StrEnum):
    LINUX = "Linux"
    WINDOWS = "Windows"
    MACOS = "macOS"
    POSIX = "POSIX"
    UNIVERSAL = "universal"


def default_checks_config() -> Mapping[str, CheckConfiguration]:
    from .checks.all import ALL_CHECKS  # local import because .checks.all imports all checks which will import this module

    return dict((check.name, check.default_config.copy()) for check in ALL_CHECKS)


@dataclass
class Configuration:
    checks: Mapping[str, CheckConfiguration] = field(default_factory=default_checks_config)
    library: Path = Path(".")
    rescan: RescanOption = RescanOption.AUTO
    tagger: str = ""
    open_folder_command: str = ""
    path_compatibility: PathCompatibilityOption = PathCompatibilityOption.UNIVERSAL

    def to_values(self) -> Mapping[str, Union[str, int, float, bool, Sequence[str]]]:
        values: Dict[str, Union[str, int, float, bool, Sequence[str]]] = {
            "settings.library": str(self.library),
            "settings.rescan": str(self.rescan),
            "settings.tagger": self.tagger,
            "settings.open_folder_command": self.open_folder_command,
            "settings.path_compatibility": str(self.path_compatibility),
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
    def from_values(cls, values: Iterator[Tuple[str, Union[str, int, float, bool, Sequence[str]]]]):
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
                    config.path_compatibility = PathCompatibilityOption(value)
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
