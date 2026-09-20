import logging
from typing import Any, Final

from rich.markup import escape
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult
from albums.entities import Album
from albums.tagger import AlbumTaggerProvider

logger: Final = logging.getLogger(__name__)


class CheckAlbumUnderAlbum(Check):
    """Check that no album folder is inside another album folder.

    Deliberately breaks the stateless check guideline (see docs/developing.md): albums are checked
    in path order, and a path that is under an earlier album is also under the most recent passing
    album (a path sorted between an album path and a longer path sharing it must share it too), so
    the check keeps just that one path and needs no queries. A filtered run may miss albums whose
    parent album is not part of the run.
    """

    name = "album-under-album"
    default_config = {"enabled": True}
    must_pass_checks = {"duplicate-folder-name"}

    def __init__(self, ctx: Context, tagger: AlbumTaggerProvider | None = None, session: Session | None = None):
        super().__init__(ctx, tagger, session)
        # most recent album path that is not under another album; None before the first album
        self._under: str | None = None

    def init(self, check_config: dict[str, Any]):
        # the CLI always sets ctx.is_filtered; contexts built for tests may not have it
        if getattr(self.ctx, "is_filtered", False):
            logger.info("filtered run: album-under-album only sees included albums and may not find nested albums")

    def check(self, album: Album) -> CheckResult | None:
        # a failing album never changes _under, so every album in the current run of child albums
        # is reported against the album their run started under; an album is never under itself
        # (a re-run after a fix sees its own path again)
        path = album.path
        if self._under is not None and path.startswith(self._under) and path != self._under:
            return CheckResult(f"in a directory under album {escape(self._under)}")
        self._under = path
        return None
