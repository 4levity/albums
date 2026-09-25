"""Application context containing shared state used by application commands.

This module defines the ``Context`` type that carries settings, database access
and console output between the various album-checking and management subcommands, plus
precondition checks (``require_*``) shared by every frontend.
"""

from pathlib import Path
from typing import Any, Callable, Iterator, Self

from rich.console import Console
from rich.markup import escape
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from .config import Configuration
from .entities import Album
from .errors import OperationError


class Context(dict[Any, Any]):
    """Mutable namespace carrying application state across CLI invocations.

    Inherits from ``dict`` because Click's persistent context machinery requires it.
    Use attribute access for the typed members listed below.

    Attributes:
        parent: Parent context if this command operates in a separate context, or ``None``.
        console: Shared rich ``Console`` instance used for all terminal output.
        db: SQLite ``Engine`` connected to the albums database.
        db_path: Absolute path to the on-disk database file.
        select_album_entities: Callable returning an iterator over ``Album`` objects for
            the current command invocation, respecting any active collection or album filters.
        is_filtered: Whether a user-provided filter narrowed the selection.
        config: Stored application configuration, loaded from the database. Only commands that
            change the persistent configuration mutate it; check runs use a working copy.
        verbose: Logging verbosity level (number of ``-v`` flags on the command line).
        is_persistent: Always ``True`` for this context class so Click keeps it alive between groups.
    """

    is_persistent = True  # required by Click to propagate context across group subcommands
    console = Console()  # intentional single shared Console

    # attributes initialized with default values that may need to be changed after instantiation
    parent: Self | None
    verbose: int
    config: Configuration

    # attributes that must be set after instantiation
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
        self.config = Configuration()


def require_configured(ctx: Context) -> None:
    """Raise OperationError if the albums database file does not exist yet (run ``albums init``)."""
    if not ctx.db_path.is_file():
        raise OperationError("This command requires albums to be configured - run [bold]albums init[/bold] to continue")


def require_library(ctx: Context) -> None:
    """Raise OperationError if the configured library directory does not exist."""
    if not ctx.config.library.is_dir():
        raise OperationError(f"Library directory does not exist: {escape(str(ctx.config.library))}")


def require_persistent_context(ctx: Context) -> None:
    """Raise OperationError if the context is a transient (``--dir``) context the command cannot use."""
    if not ctx.is_persistent:
        raise OperationError("This command cannot be used with the [bold]--dir[/bold] option")


def require_real_context(ctx: Context) -> None:
    """Raise OperationError if the command has neither a persistent database nor a ``--dir`` folder context."""
    if not ctx.is_persistent and ctx.parent is None:
        raise OperationError(
            "This command requires specifying a folder with [bold]--dir[/bold] or setting up a library with [bold]albums init[/bold]"
        )
