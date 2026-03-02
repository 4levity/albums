import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum, auto
from pathlib import Path
from typing import Collection, Dict, Iterator, Mapping, Union

from .types import CheckConfiguration, Sequence, Tuple

logger = logging.getLogger(__name__)


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


DEFAULT_IMPORT_PATH = "$A1/$artist/$album"
DEFAULT_IMPORT_PATH_LIST = ("Compilations", "Soundtracks")


def default_checks_config() -> Mapping[str, CheckConfiguration]:
    from .checks.all import ALL_CHECKS  # local import because .checks.all imports all checks which will import this module

    return dict((check.name, check.default_config.copy()) for check in ALL_CHECKS)


@dataclass
class Configuration:
    checks: Mapping[str, CheckConfiguration] = field(default_factory=default_checks_config)
    import_path_default_T: str = DEFAULT_IMPORT_PATH
    import_paths_T: Collection[str] = DEFAULT_IMPORT_PATH_LIST
    library: Path = Path(".")
    open_folder_command: str = ""
    path_compatibility: PathCompatibilityOption = PathCompatibilityOption.UNIVERSAL
    rescan: RescanOption = RescanOption.AUTO
    tagger: str = ""

    def to_values(self) -> Mapping[str, Union[str, int, float, bool, Sequence[str]]]:
        values: Dict[str, Union[str, int, float, bool, Sequence[str]]] = {
            "settings.import_path_default": str(self.import_path_default_T),
            "settings.import_paths": [path_T for path_T in self.import_paths_T],
            "settings.library": str(self.library),
            "settings.open_folder_command": self.open_folder_command,
            "settings.path_compatibility": str(self.path_compatibility),
            "settings.rescan": str(self.rescan),
            "settings.tagger": self.tagger,
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
                if name == "import_path_default":
                    config.import_path_default_T = str(value)
                    # TODO validate templates
                if name == "import_paths":
                    if isinstance(value, list):
                        config.import_paths_T = tuple(value)
                    else:
                        logger.warning(f"ignoring {k}={str(value)}, not a list of strings - using default {json.dumps(config.import_paths_T)}")
                        ignored_values = True
                if name == "library":
                    config.library = Path(str(value))
                elif name == "open_folder_command":
                    config.open_folder_command = str(value)
                elif name == "path_compatibility":
                    config.path_compatibility = PathCompatibilityOption(value)
                elif name == "rescan":
                    config.rescan = RescanOption(value)
                elif name == "tagger":
                    config.tagger = str(value)
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
