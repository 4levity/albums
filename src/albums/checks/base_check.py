from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable

from .. import app
from ..types import Album


@dataclass
class Fixer:
    fix: Callable[[str], bool]
    options: list[str]  # at least one option should be provided if "free text" is not an option
    option_free_text: bool = False
    option_automatic_index: int | None = None
    table: tuple[list[str], list[list[str]]] | None = None  # tuple (headers, row data)
    prompt: str = "select an option"  # e.g. "select an album artist for all tracks"


class ProblemCategory(Enum):
    TAGS = auto()  # issues with tags
    FILENAMES = auto()  # track filenames
    FOLDERS = auto()  # organization, folder names
    OTHER = auto()  # general problems with the album


@dataclass(frozen=True)
class CheckResult:
    category: ProblemCategory
    message: str
    fixer: Fixer | None = None


class Check:
    # subclass must override to define static check_name and default_config
    name: str
    default_config: dict[str, Any]

    # subclass may use these instance values
    ctx: app.Context
    check_config: dict[str, Any]

    # subclass may override __init__ but must retain signature
    def __init__(self, ctx: app.Context):
        self.ctx = ctx
        self.check_config = ctx.config.get("checks", {}).get(self.name, self.default_config)

    # subclass must override check()
    def check(self, album: Album) -> CheckResult | None:
        raise NotImplementedError(f"check not implemented for {self.name}")
