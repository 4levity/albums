from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from albums.app import Context
from albums.entities import Album
from albums.tagger import AlbumTaggerProvider

from .check_types import CheckConfiguration, CheckResult


class Check:
    """Base class for checks that validate and optionally fix album metadata.

    Subclasses must define static ``name`` and ``default_config``, and must override
    :meth:`check` to return a :class:`CheckResult` for an album (or ``None`` when it passes).
    They may define static ``must_pass_checks`` (names of other checks that must pass first)
    and override :meth:`init` for configuration validation or other one-time initialization.
    The ``ctx``, ``session`` and ``tagger`` instance values are available to subclasses.
    """

    name: str
    default_config: dict[str, Any]

    must_pass_checks: set[str] = set()

    ctx: Context
    session: Session
    tagger: AlbumTaggerProvider

    def check(self, album: Album) -> CheckResult | None:
        raise NotImplementedError(f"check not implemented for {self.name}")

    def init(self, check_config: CheckConfiguration):
        pass

    def __init__(self, ctx: Context, tagger: AlbumTaggerProvider | None = None, session: Session | None = None):
        self.ctx = ctx
        # note "real" non-test code should always provide tagger and managed session
        self.tagger = tagger if tagger else AlbumTaggerProvider(ctx.config.library, id3v1=ctx.config.id3v1)
        self.session = session if session else (Session(ctx.db) if hasattr(ctx, "db") else Session())
        self.init(ctx.config.checks[self.name])
