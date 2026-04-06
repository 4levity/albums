from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum, auto
from pathlib import Path
from string import Template
from typing import Dict, Iterator, List, Mapping, Sequence, Tuple, Union

from platformdirs import PlatformDirs
from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from .database.orm import Base, SerializableValueAsJson
from .types import CheckConfiguration

logger = logging.getLogger(__name__)

PLATFORM_DIRS = PlatformDirs("albums", "4levity")


type SerializedSyncDestination = dict[str, Union[str, int, float, bool, Sequence[str]]]
type SettingValueType = Union[str, int, float, bool, Sequence[str], Sequence[SerializedSyncDestination]]


class SettingEntity(Base):
    __tablename__ = "setting"

    name: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    value: Mapped[SettingValueType] = mapped_column("value_json", SerializableValueAsJson[SettingValueType], nullable=False)


class PathCompatibilityOption(StrEnum):
    LINUX = "Linux"
    WINDOWS = "Windows"
    MACOS = "macOS"
    POSIX = "POSIX"
    UNIVERSAL = "universal"


class RescanOption(StrEnum):
    ALWAYS = auto()
    NEVER = auto()
    AUTO = auto()


DEFAULT_IMPORT_PATH = Template("$artist/$album")
DEFAULT_IMPORT_PATH_VARIOUS = Template("Compilations/$album")
DEFAULT_MORE_IMPORT_PATHS = (Template("$A1/$artist/$album"), Template("Soundtracks/$album"))
DEFAULT_IMPORT_SCAN_MAX_PATHS = 250


def default_checks_config() -> Mapping[str, CheckConfiguration]:
    from .checks.all import ALL_CHECKS  # local import because .checks.all imports all checks which will import this module

    return dict((check.name, check.default_config.copy()) for check in ALL_CHECKS)


class ID3v1Policy(IntEnum):
    # Do not change, these are the values used by mutagen MP3.save()
    REMOVE = 0
    UPDATE = 1
    CREATE = 2


DEFAULT_FILE_CONVERT_PROFILE = "mp3"


@dataclass
class SyncDestination:
    collection: str
    path_root: Path
    relpath_template_artist: Template = Template("")
    relpath_template_compilation: Template = Template("")
    allow_file_types: List[str] = field(default_factory=list[str])
    convert_profile: str = DEFAULT_FILE_CONVERT_PROFILE
    max_kbps: int = 0

    def __str__(self) -> str:
        return f"{self.collection} -> {self.path_root}"

    def __lt__(self, other: SyncDestination):
        return self.collection < other.collection or (self.collection == other.collection and str(self.path_root) < str(other.path_root))

    def to_dict(self) -> SerializedSyncDestination:
        return {
            "collection": self.collection,
            "path_root": str(self.path_root),
            "relpath_template_artist": self.relpath_template_artist.template,
            "relpath_template_compilation": self.relpath_template_compilation.template,
            "allow_file_types": self.allow_file_types,
            "convert_profile": self.convert_profile,
            "max_kbps": self.max_kbps,
        }

    @classmethod
    def from_dict(cls, values: SerializedSyncDestination):
        return SyncDestination(
            str(values["collection"]),
            Path(str(values["path_root"])),
            Template(str(values.get("relpath_template_artist", ""))),
            Template(str(values.get("relpath_template_compilation", ""))),
            values["allow_file_types"] if ("allow_file_types" in values and isinstance(values["allow_file_types"], list)) else [],
            str(values.get("convert_profile", DEFAULT_FILE_CONVERT_PROFILE)),
            int(str(values.get("max_kbps", 0))),
        )


@dataclass
class Configuration:
    checks: Mapping[str, CheckConfiguration] = field(default_factory=default_checks_config)
    default_import_path: Template = DEFAULT_IMPORT_PATH
    default_import_path_various: Template = DEFAULT_IMPORT_PATH_VARIOUS
    more_import_paths: Sequence[Template] = DEFAULT_MORE_IMPORT_PATHS
    import_scan_max_paths: int = DEFAULT_IMPORT_SCAN_MAX_PATHS
    library: Path = Path(".")
    transcoder_cache: Path = PLATFORM_DIRS.user_data_path / "albums_transcoder_cache"
    transcoder_cache_size: int = 16 * pow(2, 30)  # 16 GiB
    open_folder_command: str = ""
    path_compatibility: PathCompatibilityOption = PathCompatibilityOption.UNIVERSAL
    path_replace_slash = "-"
    path_replace_invalid = ""
    rescan: RescanOption = RescanOption.AUTO
    tagger: str = ""
    id3v1: ID3v1Policy = ID3v1Policy.UPDATE
    sync_destinations: List[SyncDestination] = field(default_factory=list[SyncDestination])

    def to_values(self) -> Mapping[str, SettingValueType]:
        values: Dict[str, SettingValueType] = {
            "settings.default_import_path": self.default_import_path.template,
            "settings.default_import_path_various": self.default_import_path_various.template,
            "settings.more_import_paths": [path_T.template for path_T in self.more_import_paths],
            "settings.import_scan_max_paths": self.import_scan_max_paths,
            "settings.library": str(self.library),
            "settings.transcoder_cache": str(self.transcoder_cache),
            "settings.transcoder_cache_size": self.transcoder_cache_size,
            "settings.open_folder_command": self.open_folder_command,
            "settings.path_compatibility": self.path_compatibility.value,
            "settings.path_replace_invalid": str(self.path_replace_invalid),
            "settings.path_replace_slash": str(self.path_replace_slash),
            "settings.rescan": str(self.rescan),
            "settings.tagger": self.tagger,
            "settings.id3v1": self.id3v1.value,
            "settings.sync_destinations": [dest.to_dict() for dest in self.sync_destinations],
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
    def from_values(cls, values: Iterator[Tuple[str, SettingValueType]]):
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
                # TODO validate templates
                if name == "default_import_path":
                    config.default_import_path = Template(str(value))
                elif name == "default_import_path_various":
                    config.default_import_path_various = Template(str(value))
                elif name == "more_import_paths":
                    if isinstance(value, list) and all(isinstance(item, str) for item in value):
                        config.more_import_paths = tuple(Template(v) for v in value)  # pyright: ignore[reportArgumentType]
                    else:
                        logger.warning(f"ignoring {k}={str(value)}, not a list of strings - using default {json.dumps(config.more_import_paths)}")
                        ignored_values = True
                elif name == "import_scan_max_paths":
                    max_paths = str(value)
                    if str.isdecimal(max_paths):
                        config.import_scan_max_paths = int(max_paths)
                    else:
                        logger.warning(f"ignoring {k}={max_paths}, not a number - using default {config.import_scan_max_paths}")
                        ignored_values = True
                elif name == "library":
                    config.library = Path(str(value))
                elif name == "transcoder_cache":
                    config.transcoder_cache = Path(str(value))
                elif name == "transcoder_cache_size":
                    config.transcoder_cache_size = int(str(value))
                elif name == "open_folder_command":
                    config.open_folder_command = str(value)
                elif name == "path_compatibility":
                    config.path_compatibility = PathCompatibilityOption(value)
                elif name == "path_replace_invalid":
                    config.path_replace_invalid = str(value)
                elif name == "path_replace_slash":
                    config.path_replace_slash = str(value)
                elif name == "rescan":
                    config.rescan = RescanOption(value)
                elif name == "tagger":
                    config.tagger = str(value)
                elif name == "id3v1":
                    config.id3v1 = ID3v1Policy(value)
                elif name == "sync_destinations":
                    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                        config.sync_destinations = [SyncDestination.from_dict(dest) for dest in value]  # pyright: ignore[reportArgumentType]
                    else:
                        logger.warning(f"ignoring {k}={str(value)}, not a list of sync destination dictionaries")
                        ignored_values = True
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
                elif not isinstance(value, list) or all(isinstance(item, str) for item in value):
                    config.checks[section][name] = value  # pyright: ignore[reportArgumentType]
        return (config, ignored_values)
