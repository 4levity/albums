"""Application context containing shared state used by application commands.

This module defines the ``Context`` type that carries settings, database access
and console output between the various album-checking and management subcommands.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Final, Iterator, Self

import click
from rich.console import Console
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from .config import Configuration
from .types import Album

logger: Final = logging.getLogger(__name__)

# Bumped whenever the database schema or scan logic changes incompatibly.
SCANNER_VERSION: Final = 9


class Context(dict[Any, Any]):
    """Mutable namespace carrying application state across CLI invocations.

    Inherits from ``dict`` because Click's persistent context machinery requires it.
    Use attribute access for the typed members listed below.

    Attributes:
        parent: Parent context if this command operates in a separate context, or ``None``.
        console: Shared rich ``Console`` instance used for all terminal output.
        click_ctx: The underlying Click ``Context`` (``None`` only during tests).
        db: SQLite ``Engine`` connected to the albums database.
        db_path: Absolute path to the on-disk database file.
        select_album_entities: Callable returning an iterator over ``Album`` objects for
            the current command invocation, respecting any active collection or album filters.
        is_filtered: Whether a user-provided filter narrowed the selection.
        config: Loaded application configuration (defaults + CLI overrides).
        verbose: Logging verbosity level (number of ``-v`` flags on the command line).
        is_persistent: Always ``True`` for this context class so Click keeps it alive between groups.
        prescanned: Whether a full-library scan has already been performed in this session.
        importing: ``True`` while running album import commands that mutate library folders.
    """

    parent: Self | None = None
    console = Console()  # single shared Console
    click_ctx: click.Context | None
    db: Engine
    db_path: Path
    select_album_entities: Callable[[Session], Iterator[Album]]
    is_filtered: bool
    config: Configuration
    verbose: int = 0
    is_persistent = True  # required by Click to propagate context across group subcommands
    prescanned = False
    importing = False

    def __init__(self, *args, **kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        """Initialize a fresh application context with default configuration.

        Arbitrary keyword arguments are forwarded to ``dict.__init__`` for legacy Click compatibility.
        """
        super(Context, self).__init__(*args, **kwargs)
        self.config = Configuration()
