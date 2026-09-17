"""Check that no element of an album path has a sibling folder that differs only in case."""

import logging
import os

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult
from albums.entities import Album, LibraryFolder
from albums.tagger import AlbumTaggerProvider

logger = logging.getLogger(__name__)


class CheckDuplicateFolderName(Check):
    """Check that no folder in an album path has a sibling folder whose name differs only in case.

    Example: "Artist/Album/" and "Artist/album/" (or "Artist/" and "artist/") can coexist on a
    case-sensitive file system, but such pairs break case-insensitive pathing and conflict in
    synced copies. The check flags the album but offers no automatic fix: renaming folders that
    differ only in case can be dangerous on some file systems or mounts, and a full scan is
    needed after a manual rename to refresh the check's data.

    The check holds non-configuration state (``_conflicts``), like ``duplicate-album``, because it
    must compare each album against folders across the whole library. Building the index is much
    lighter than duplicate-album's, though: a single grouped query over the ``library_folder``
    table (maintained by the full scan) returns only the (parent path, casefolded name) pairs
    involved in case conflicts - usually none - plus one small indexed lookup per conflicting
    pair, and ``check()`` then tests the album's few path elements against that small set, without
    any file system access.
    """

    name = "duplicate-folder-name"
    default_config = {"enabled": True}

    _conflicts: dict[str, set[str]]

    def __init__(self, ctx: Context, tagger: AlbumTaggerProvider | None = None, session: Session | None = None):
        super().__init__(ctx, tagger, session)
        # parent path -> names of the folders in it that have a case-differing sibling
        self._conflicts = {}
        for parent_path, name_cf in self.session.execute(
            select(LibraryFolder.parent_path, LibraryFolder.name_cf)
            .group_by(LibraryFolder.parent_path, LibraryFolder.name_cf)
            .having(func.count() > 1)
        ).tuples():
            # note: select the names for each conflicting pair separately - name is not a group key, so it cannot
            # be selected in the grouped query (SQLite would return an arbitrary name from each group)
            names = [
                name
                for (name,) in self.session.execute(
                    select(LibraryFolder.name).where(and_(LibraryFolder.parent_path == parent_path, LibraryFolder.name_cf == name_cf))
                ).tuples()
            ]
            self._conflicts[parent_path] = set(names)

    def check(self, album: Album) -> CheckResult | None:
        if not self._conflicts:
            return None
        issues: list[str] = []
        parent = ""
        for element in (segment for segment in album.path.split(os.sep) if segment):
            siblings = self._conflicts.get(parent)
            if siblings is not None and element in siblings:
                others = sorted(siblings - {element})
                issues.append(f'"{parent}{element}" and {", ".join(f'"{parent}{sibling}"' for sibling in others)} differ only in case')
            parent += f"{element}{os.sep}"
        if issues:
            return CheckResult(f"duplicate folder names: {', '.join(issues)}")
        return None
