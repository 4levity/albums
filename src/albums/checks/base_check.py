from __future__ import annotations
from dataclasses import dataclass

from .. import app
from ..types import Album
from .base_fixer import Fixer


@dataclass(frozen=True)
class CheckResult:
    name: str
    message: str
    fixer: Fixer | None = None


class Check:
    # subclass must define static name and default_config
    name: str
    default_config: dict

    # subclass may use these instance values
    ctx: app.Context
    config: str

    def __init__(self, ctx: app.Context):
        self.ctx = ctx
        self.config = ctx.config.get("checks", {}).get(self.name, self.default_config)

    def check(self, album: Album) -> CheckResult | None:
        return None
