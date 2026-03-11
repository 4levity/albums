from __future__ import annotations

from typing import Any

from ..app import Context
from ..database.models import AlbumEntity
from ..tagger.provider import AlbumTaggerProvider
from ..types import CheckConfiguration, CheckResult


class Check:
    # subclass must override to define static check_name and default_config
    name: str
    default_config: dict[str, Any]
    tagger: AlbumTaggerProvider

    # subclass may override to define static dependencies on other checks passing first
    must_pass_checks: set[str] = set()

    # subclass may use these instance values
    ctx: Context

    # subclass must override check()
    def check(self, album: AlbumEntity) -> CheckResult | None:
        raise NotImplementedError(f"check not implemented for {self.name}")

    # subclass should override init if there is configuration to validate or other one-time initialization
    def init(self, check_config: CheckConfiguration):
        pass

    def __init__(self, ctx: Context, tagger: AlbumTaggerProvider | None = None):
        self.ctx = ctx
        self.tagger = tagger if tagger else AlbumTaggerProvider(ctx.config.library, id3v1=ctx.config.id3v1)
        self.init(ctx.config.checks[self.name])
