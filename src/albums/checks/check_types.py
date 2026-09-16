"""Shared type definitions for check/fixer contracts and result reporting."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Dict, Iterable, Sequence, Tuple, Union

from rich.console import RenderableType

# Mapping type representing the configuration items available for a single registered check.
type CheckConfiguration = Dict[str, Union[str, int, float, bool, Sequence[str]]]


class FixResult(Enum):
    """Outcome of a fix callback; tells the ``Checker`` what to do next (see the Fixers section of docs/developing.md)."""

    NO_CHANGE = auto()  # Nothing changed: no re-scan, no commit.
    CHANGED_ALBUM = auto()  # This album changed; the ``Checker`` re-scans it from disk and commits.
    DELETED_ALBUM = auto()  # This album was deleted from disk; its rows are removed now and committed at the end of the run.
    CHANGED_OTHER = auto()  # Something outside this album changed (e.g. a duplicate album deleted); re-scan and commit.

    @staticmethod
    def of(changed: bool) -> "FixResult":
        """Convenience factory mapping a boolean to either ``NO_CHANGE`` or ``CHANGED_ALBUM``.

        Args:
            changed: ``True`` when the fix mutated library state.

        Returns:
            ``CHANGED_ALBUM`` if *changed* else ``NO_CHANGE``.
        """
        return FixResult.CHANGED_ALBUM if changed else FixResult.NO_CHANGE


@dataclass
class Fixer:
    """Encapsulates a proposed correction along with user-interface hints for interactive mode.

    When a check detects a problem, it may attach a *Fixer* to the ``CheckResult`` so the system
    (or an interactive terminal prompt) can present options and apply the chosen fix.

    Attributes:
        fix: Callable accepting a selected option string and returning a ``FixResult``.
        options: Human-readable choices presented to the user; must have at least one entry when free text is disabled.
        option_free_text: When ``True``, offer the user an arbitrary text value in addition to *options*.
        option_automatic_index: Index into *options* representing the automatic choice or None if no automatic choice.
        table: Optional tabular data (headers + rows or row-factory callable) to display alongside options.
        prompt: Text displayed above the options when asking for user input.

    Contract (details in the Fixers section of docs/developing.md):
        - Persist all file changes to disk: after an applied fix the album is re-scanned
          (``reread=True``) and its database rows are rebuilt from the files, so ORM-only
          edits to file-derived data (e.g. ``track.fields``) are reverted.
        - Mutate ORM entities directly only for metadata not stored in the files, which
          the re-scan leaves alone (e.g. ``PictureFile.cover_source``, ``Album.collections``,
          ``Album.ignore_checks``).
        - Return the matching ``FixResult``: the ``Checker`` re-scans and commits for
          changes, while a ``DELETED_ALBUM`` deletion is committed at the end of the run
          (stale rows self-heal on the next run if the run is interrupted).
        - Never call ``session.commit()``; the ``Checker`` owns the transaction.
    """

    fix: Callable[[str], FixResult]
    options: Sequence[str]
    option_free_text: bool = False
    option_automatic_index: int | None = None
    table: Tuple[Iterable[str], Iterable[Iterable[RenderableType]] | Callable[[], Iterable[Iterable[RenderableType]]]] | None = None
    prompt: str = "select an option"  # e.g. "select an album artist for all tracks"

    def get_table(self) -> Tuple[Iterable[str], Iterable[Iterable[RenderableType]]] | None:
        """Resolve the table hint into concrete headers and row data.

        If the stored rows were a lazy factory, they are invoked here so checks that defer expensive
        computation can remain fast unless an interactive prompt actually renders.

        Returns:
            A ``(headers, rows)`` tuple or ``None`` when no table was configured.
        """
        if self.table is None:
            return None
        (headers, get_rows) = self.table
        rows: Iterable[Iterable[RenderableType]] = get_rows if isinstance(get_rows, Iterable) else get_rows()  # pyright: ignore[reportUnknownVariableType]
        return (headers, rows)


@dataclass(frozen=True)
class CheckResult:
    """Outcome returned by check implementations to signal a problem that needs attention.

    Attributes:
        message: Human-readable description of what is wrong or missing for the album.
        fixer: Optional correction proposal; when ``None`` the user must handle the issue manually.
    """

    message: str
    fixer: Fixer | None = None
