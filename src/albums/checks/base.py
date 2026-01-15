from __future__ import annotations
from dataclasses import dataclass
import sqlite3

from ..context import AppContext
from ..types import Album
from .defaults import ALL_CHECKS_DEFAULT


@dataclass(frozen=True)
class CheckResult:
    name: str
    message: str
    can_autofix: bool = False
    next: CheckResult | None = None
    # TODO fixes that require user input

    def autofix():
        pass


class Check:
    # subclass must define static name and default_config
    name: str
    default_config: str

    # subclass may use these instance values
    db: sqlite3.Connection
    config: str

    def __init__(self, ctx: AppContext):
        self.db = ctx.db
        self.config = ctx.config.get("checks", {}).get(self.name, ALL_CHECKS_DEFAULT[self.name])

    def check(self, album: Album) -> CheckResult | None:
        return None
