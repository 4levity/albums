"""Build and manage the application context for CLI commands, including album filtering and database setup."""

import logging
import os
from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from functools import reduce
from pathlib import Path
from typing import Final, List, Sequence

import click
from rich.logging import RichHandler
from rich.markup import escape

from albums.app import Context
from albums.config import PLATFORM_DIRS, RescanOption, config_load
from albums.database import MEMORY, db_open
from albums.errors import OperationError
from albums.selector import Comparator, Match

logger: Final = logging.getLogger(__name__)


pass_context: Final = click.make_pass_decorator(Context, ensure=True)


DEFAULT_DB_LOCATION: Final = str(PLATFORM_DIRS.user_config_path / "albums.db")


@dataclass(frozen=True)
class FilterCriteria:
    """A single filter on album fields, built from a ``K[op]V`` expression such as ``artist=Some Artist`` or ``path~=^sub/``."""

    field: str
    value: str
    comparator: Comparator = Comparator.EQ

    @classmethod
    def from_expr(cls, expr: str):
        """Parse a ``K[op]V`` expression (field, optional Comparator operator, value) into FilterCriteria; a bare ``K`` means the field must exist."""
        comparator = next((comparator for comparator in Comparator if comparator.value in expr), None)
        (field, _, value) = expr.partition(comparator.value) if comparator else (expr, "", "")
        return cls(field, value, comparator or Comparator.EQ)


def setup(
    ctx: click.Context,
    app_context: Context,
    verbose: int,
    filter_criteria: Sequence[FilterCriteria],
    dir: str,
    invert: bool,
    db_file: str | None,
):
    """Prepare the application context for a command run.

    Configures logging, resolves and opens the albums database (falling back to an in-memory database when none is
    found), and stores the command line album selection parameters built from *filter_criteria* and *invert*.
    When *dir* is given, the context is reconfigured via :func:`enter_folder_context` to operate on that folder
    instead of the library database.

    Returns:
        ``True`` when an initial full library scan should be run first (a ``--dir`` folder context was used, or the
        rescan policy is ``ALWAYS``).
    """
    app_context.verbose = verbose
    _setup_logging(app_context, verbose)
    logger.info("starting albums")

    app_context.db_path = _get_albums_db_path(db_file)
    if app_context.db_path.is_file():
        app_context.db = _open_db_and_set_context_config(ctx, app_context)
        has_database = True
    else:
        has_database = False
        if not dir:
            logger.info("the --dir option is not specified and albums database is not found")

    filter: defaultdict[str, List[Match]] = defaultdict(list)
    filter = reduce(lambda acc, kv: acc[kv.field].append(Match(kv.value, kv.comparator)) or acc, filter_criteria, filter)
    app_context.set_album_selection(filter, invert)
    if dir:
        enter_folder_context(app_context, dir)
    elif not has_database:
        # it's simpler to always give app_context a database than to allow it to be Engine | None.
        # the in-memory engine has no file to release: it is cleaned up when the process exits, so no dispose is needed
        app_context.is_persistent = False
        app_context.db = db_open(MEMORY, echo=False)
    return bool(dir) or app_context.config.rescan == RescanOption.ALWAYS


def enter_folder_context(ctx: Context, folder: str) -> Context:
    """Reconfigure *ctx* to operate on *folder* with a fresh in-memory database.

    A shallow copy of the original context is taken before any changes and stored in ``ctx.parent``; that untouched
    parent copy (not the reconfigured context) is returned. The context's configuration is shallow-copied with its
    library set to *folder*; the stored configuration is not changed. The album selection is reset to all albums in
    the folder; any command line filter is ignored.
    """
    if ctx.parent:
        raise RuntimeError("enter_folder_context called on subcontext")
    parent = copy(ctx)
    ctx.parent = parent
    ctx.config = copy(parent.config)
    ctx.config.library = Path(folder)
    if not ctx.config.library.is_dir():
        raise OperationError(f"directory does not exist: {escape(str(ctx.config.library))}")
    logger.info(f"using in-memory context, library is {folder}")

    ctx.db = db_open(MEMORY, echo=ctx.verbose > 1)
    ctx.set_album_selection()  # a folder context selects all albums in the folder, ignoring any filter
    ctx.is_persistent = False
    return parent


def _get_albums_db_path(db_file: str | None):
    if db_file is not None:
        album_db_file = db_file
    elif "ALBUMS_DB" in os.environ:
        album_db_file = os.environ["ALBUMS_DB"]
    elif Path("albums.db").is_file():
        album_db_file = "albums.db"
    else:
        album_db_file = DEFAULT_DB_LOCATION
    return Path(album_db_file)


def _open_db_and_set_context_config(ctx: click.Context, app_context: Context):
    logger.info(f"using database {str(app_context.db_path)}")
    db = db_open(app_context.db_path, echo=app_context.verbose > 1)
    ctx.call_on_close(lambda: db.dispose())
    app_context.config = config_load(db)
    return db


def _setup_logging(ctx: Context, verbose: int):
    log_format = "%(message)s"
    rich = RichHandler(show_time=False, show_level=True, console=ctx.console)
    if verbose >= 2:
        logging.basicConfig(level=logging.DEBUG, format=log_format, handlers=[rich])
    elif verbose == 1:
        logging.basicConfig(level=logging.INFO, format=log_format, handlers=[rich])
    else:
        logging.basicConfig(level=logging.WARNING, format=log_format, handlers=[rich])
    logging.captureWarnings(True)
