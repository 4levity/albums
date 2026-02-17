from __future__ import annotations

from typing import Any

from ..app import Context
from ..types import Album, CheckConfiguration, CheckResult


class Check:
    # subclass must override to define static check_name and default_config
    name: str
    default_config: dict[str, Any]

    # subclass may override to define static dependencies on other checks passing first
    must_pass_checks: set[str] = set()

    # subclass may use these instance values
    ctx: Context

    # subclass must override check()
    def check(self, album: Album) -> CheckResult | None:
        raise NotImplementedError(f"check not implemented for {self.name}")

    # subclass should override init if there is configuration to validate or other one-time initialization
    def init(self, check_config: CheckConfiguration):
        pass

    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.init(ctx.config.checks[self.name])
