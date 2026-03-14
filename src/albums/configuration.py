import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum, auto
from pathlib import Path
from string import Template
from typing import Dict, Iterator, Mapping, Union

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from .database.orm import Base, SerializableValueAsJson
from .tagger.base_id3 import ID3v1Policy
from .types import CheckConfiguration, Sequence, Tuple

logger = logging.getLogger(__name__)


type SettingValueType = Union[str, int, float, bool, Sequence[str]]


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


def default_checks_config() -> Mapping[str, CheckConfiguration]:
    from .checks.all import ALL_CHECKS  # local import because .checks.all imports all checks which will import this module

    return dict((check.name, check.default_config.copy()) for check in ALL_CHECKS)


@dataclass
class Configuration:
    checks: Mapping[str, CheckConfiguration] = field(default_factory=default_checks_config)
    default_import_path: Template = DEFAULT_IMPORT_PATH
    default_import_path_various: Template = DEFAULT_IMPORT_PATH_VARIOUS
    more_import_paths: Sequence[Template] = DEFAULT_MORE_IMPORT_PATHS
    library: Path = Path(".")
    open_folder_command: str = ""
    path_compatibility: PathCompatibilityOption = PathCompatibilityOption.UNIVERSAL
    path_replace_slash = "-"
    path_replace_invalid = ""
    rescan: RescanOption = RescanOption.AUTO
    tagger: str = ""
    id3v1: ID3v1Policy = ID3v1Policy.UPDATE

    def to_values(self) -> Mapping[str, SettingValueType]:
        values: Dict[str, Union[str, int, float, bool, Sequence[str]]] = {
            "settings.default_import_path": self.default_import_path.template,
            "settings.default_import_path_various": self.default_import_path_various.template,
            "settings.more_import_paths": [path_T.template for path_T in self.more_import_paths],
            "settings.library": str(self.library),
            "settings.open_folder_command": self.open_folder_command,
            "settings.path_compatibility": self.path_compatibility.value,
            "settings.path_replace_invalid": str(self.path_replace_invalid),
            "settings.path_replace_slash": str(self.path_replace_slash),
            "settings.rescan": str(self.rescan),
            "settings.tagger": self.tagger,
            "settings.id3v1": self.id3v1.value,
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
                    if isinstance(value, list):
                        config.more_import_paths = tuple(Template(v) for v in value)
                    else:
                        logger.warning(f"ignoring {k}={str(value)}, not a list of strings - using default {json.dumps(config.more_import_paths)}")
                        ignored_values = True
                elif name == "library":
                    config.library = Path(str(value))
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
