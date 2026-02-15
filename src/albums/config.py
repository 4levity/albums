from dataclasses import dataclass
from typing import List, Union


@dataclass
class CheckConfiguration:
    enabled: bool
    settings: dict[str, Union[str, int, bool, List[str]]]


@dataclass
class Configuration:
    settings: dict[str, Union[str, int, bool, List[str]]]
    checks: dict[str, CheckConfiguration]


DEFAULT_SETTINGS = {"library": "", "rescan": "auto", "tagger": "", "open_folder_command": ""}
