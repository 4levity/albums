"""Application context containing shared state used by application commands.

This module defines the ``Context`` type that carries settings, database access
and console output between the various album-checking and management subcommands.
"""

import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Final, Iterator, Mapping, Self

import click
from rich.console import Console
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from .checks.check_types import CheckConfiguration
from .config import Configuration
from .entities import Album

logger: Final = logging.getLogger(__name__)


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
        stored_checks: Deep copy of the persisted check configuration (``config.checks``) taken
            when the configuration is loaded. It represents the user's standing settings for a full
            check run and, unlike :attr:`config`, is not altered by the temporary per-invocation
            overrides that e.g. ``albums check <name>`` applies.
        verbose: Logging verbosity level (number of ``-v`` flags on the command line).
        is_persistent: Always ``True`` for this context class so Click keeps it alive between groups.
        prescanned: Whether a full-library scan has already been performed in this session.
        importing: ``True`` while running album import commands that mutate library folders.
    """

    is_persistent = True  # required by Click to propagate context across group subcommands
    console = Console()  # intentional single shared Console

    # attributes initialized with default values that may need to be changed after instantiation
    parent: Self | None
    verbose: int
    prescanned: bool
    importing: bool
    config: Configuration
    stored_checks: Mapping[str, CheckConfiguration]

    # attributes that must be set after instantiation
    click_ctx: click.Context | None
    db: Engine
    db_path: Path
    select_album_entities: Callable[[Session], Iterator[Album]]
    is_filtered: bool

    def __init__(self, *args, **kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        """Initialize a fresh application context with default configuration.

        Arbitrary keyword arguments are forwarded to ``dict.__init__`` for legacy Click compatibility.
        """
        super(Context, self).__init__(*args, **kwargs)
        self.parent = None
        self.verbose = 0
        self.prescanned = False
        self.importing = False
        self.config = Configuration()
        self.stored_checks = deepcopy(self.config.checks)
