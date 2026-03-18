import logging
import os
import shutil
from collections import defaultdict
from copy import copy
from functools import reduce
from pathlib import Path
from typing import Sequence, Tuple

import click
from platformdirs import PlatformDirs
from rich.logging import RichHandler

from ..app import Context
from ..config import RescanOption
from ..database import connection, db_config, selector

logger = logging.getLogger(__name__)


pass_context = click.make_pass_decorator(Context, ensure=True)


PLATFORM_DIRS = PlatformDirs("albums", "4levity")
DEFAULT_DB_LOCATION = str(PLATFORM_DIRS.user_config_path / "albums.db")


def require_database(ctx: Context, command: str) -> None:
    if not ctx.db_path.is_file():
        ctx.console.print(f"[bold]{command}[/bold] requires a database")
        raise SystemExit(1)


def require_library(ctx: Context, command: str) -> None:
    if not ctx.config.library.is_dir():
        logger.error(f"directory does not exist: {str(ctx.config.library)}")
        raise SystemExit(1)


def require_persistent_context(ctx: Context, command: str) -> None:
    if not ctx.is_persistent:
        ctx.console.print(f"[bold]{command}[/bold] requires a persistent library, and cannot be used with the [bold]--dir[/bold] option.")
        raise SystemExit(1)


def setup(
    ctx: click.Context,
    app_context: Context,
    verbose: int,
    matchers_list: Sequence[Tuple[str, str]],
    dir: str,
    regex: bool,
    db_file: str | None,
):
    app_context.click_ctx = ctx
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

    if app_context.config.tagger:
        if not shutil.which(app_context.config.tagger):
            logger.warning(f'configuration specifies a tagger program "{app_context.config.tagger}" but it does not seem to be on the path')
    elif shutil.which("easytag"):  # could look for others too
        logger.debug("no external tagger configured - found easytag, using it")
        app_context.config.tagger = "easytag"

    app_context.is_filtered = bool(matchers_list)
    matchers: defaultdict[str, list[str]] = defaultdict(list)
    matchers = reduce(lambda acc, kv: acc[kv[0]].append(kv[1]) or acc, matchers_list, matchers)
    if dir:
        if "path" in matchers:
            del matchers["path"]
        enter_folder_context(app_context, dir)
    elif not has_database:
        # it's simpler to always give app_context a database than to allow it to be Engine | None
        app_context.console.print(
            "albums is not configured yet, and the [bold]--dir[/bold] was not specified. Run [bold]albums init[/bold] to remove this message."
        )
        app_context.is_persistent = False
        app_context.db = connection.open(connection.MEMORY, echo=False)
        ctx.call_on_close(lambda: app_context.db.dispose())
    app_context.select_album_entities = lambda session: selector.load_album_entities(session, regex=regex, **matchers)
    return bool(dir) or app_context.config.rescan == RescanOption.ALWAYS


def enter_folder_context(ctx: Context, folder: str):
    if ctx.parent:
        raise RuntimeError("enter_folder_context called on subcontext")
    parent = copy(ctx)
    ctx.parent = parent
    ctx.config = copy(parent.config)
    ctx.config.library = Path(folder)
    if not ctx.config.library.is_dir():
        logger.error(f"directory does not exist: {str(ctx.config.library)}")
        raise SystemExit(1)
    logger.info(f"using in-memory context, library is {folder}")

    ctx.db = connection.open(connection.MEMORY, echo=ctx.verbose > 1)
    if ctx.click_ctx:
        ctx.click_ctx.call_on_close(lambda: ctx.db.dispose())
    ctx.is_filtered = False
    ctx.is_persistent = False


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
    db = connection.open(app_context.db_path, echo=app_context.verbose > 1)
    ctx.call_on_close(lambda: db.dispose())
    app_context.config = db_config.load(db)
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
