from __future__ import annotations
from dataclasses import dataclass

from ..context import AppContext
from ..types import Album
from .base_fixer import Fixer


@dataclass(frozen=True)
class CheckResult:
    name: str
    message: str
    fixer: Fixer | None = None
    next: CheckResult | None = None
    # TODO fixes that require user input

    def autofix():
        pass


class Check:
    # subclass must define static name and default_config
    name: str
    default_config: str

    # subclass may use these instance values
    ctx: AppContext
    config: str

    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.config = ctx.config.get("checks", {}).get(self.name, self.default_config)

    def check(self, album: Album) -> CheckResult | None:
        return None
