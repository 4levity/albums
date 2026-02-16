import logging
from dataclasses import dataclass, field
from enum import StrEnum, auto
from pathlib import Path
from typing import Dict, Iterator, List, Tuple, Union

from .types import CheckConfiguration

logger = logging.getLogger(__name__)


class RescanOption(StrEnum):
    ALWAYS = auto()
    NEVER = auto()
    AUTO = auto()


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

    def to_values(self) -> Dict[str, Union[str, int, float, bool, List[str]]]:
        values: Dict[str, Union[str, int, float, bool, List[str]]] = {
            "settings.library": str(self.library),
            "settings.rescan": str(self.rescan),
            "settings.tagger": self.tagger,
            "settings.open_folder_command": self.open_folder_command,
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
        for k, value in values:
            tokens = k.split(".")
            if len(tokens) != 2:
                logger.warning(f"ignoring invalid configuration key {k} (expected section.name)")
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
                else:
                    logger.warning(f"ignoring unknown configuration item {k} = {str(value)}")
            else:
                if section not in config.checks or name not in config.checks[section]:
                    logger.warning(f"ignoring unknown configuration item {k} = {str(value)}")
                elif type(value) is not type(config.checks[section][name]):
                    logger.warning(f"ignoring configuration item {k} with wrong type {type(value)} (expected {type(config.checks[section][name])})")
                else:
                    config.checks[section][name] = value
        return config
