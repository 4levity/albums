import logging
import os
import shutil
import sqlite3
from collections import defaultdict
from copy import copy
from functools import reduce
from pathlib import Path
from typing import Sequence, Tuple

import click
from platformdirs import PlatformDirs
from prompt_toolkit.shortcuts import confirm
from rich.logging import RichHandler

from ..app import Context
from ..configuration import RescanOption
from ..database import connection, db_config, selector

logger = logging.getLogger(__name__)


pass_context = click.make_pass_decorator(Context, ensure=True)


PLATFORM_DIRS = PlatformDirs("albums", "4levity")
DEFAULT_DB_LOCATION = str(PLATFORM_DIRS.user_config_path / "albums.db")


def require_persistent_context(ctx: Context) -> sqlite3.Connection:
    if not ctx.is_persistent or not ctx.db:
        ctx.console.print("This operation acts on a persistent library and cannot be used with --dir / -d option.")
        raise SystemExit(1)
    return ctx.db


def require_library(ctx: Context) -> None:
    if not ctx.config.library.is_dir():
        logger.error(f"directory does not exist: {str(ctx.config.library)}")
        raise SystemExit(1)


def setup(
    ctx: click.Context,
    app_context: Context,
    verbose: int,
    matchers_list: Sequence[Tuple[str, str]],
    dir: str,
    regex: bool,
    new_library: str | None,
    db_file: str | None,
):
    app_context.click_ctx = ctx
    app_context.verbose = verbose
    _setup_logging(app_context, verbose)
    logger.info("starting albums")

    new_library_path: Path | None = None
    album_db_path = _get_albums_db_path(db_file)
    if album_db_path.is_file():
        if new_library:
            logger.error("the --library option may only be used when creating a database")
            raise SystemExit(1)
        db = _open_db_and_set_context_config(ctx, app_context, album_db_path)
    elif new_library:
        new_library_path = Path(new_library)
        _ensure_library_dir(new_library_path)
        db = _create_db_and_set_context_config(ctx, app_context, album_db_path, new_library_path)
    elif not dir:
        new_library_path: Path | None = None
        if PLATFORM_DIRS.user_music_path.is_dir():
            if confirm(f"No path specifed with --library, use {str(PLATFORM_DIRS.user_music_path)} ?"):
                new_library_path = PLATFORM_DIRS.user_music_path
        _ensure_library_dir(new_library_path)
        db = _create_db_and_set_context_config(ctx, app_context, album_db_path, new_library_path)
    else:
        db = None

    if app_context.config.tagger:
        if not shutil.which(app_context.config.tagger):
            logger.warning(f'configuration specifies a tagger program "{app_context.config.tagger}" but it does not seem to be on the path')
    elif shutil.which("easytag"):  # could look for others too
        logger.debug("no external tagger configured - found easytag, using it")
        app_context.config.tagger = "easytag"

    app_context.is_filtered = bool(matchers_list)
    matchers: defaultdict[str, list[str]] = defaultdict(list)
    matchers = reduce(lambda acc, kv: acc[kv[0]].append(kv[1]) or acc, matchers_list, matchers)
    if db:
        app_context.db = db
        if dir and "path" in matchers:
            del matchers["path"]
        app_context.select_albums = lambda load_track_tag: selector.load_albums(db, regex=regex, load_track_tags=load_track_tag, **matchers)

    if dir:
        enter_folder_context(app_context, dir)
    # else there is definitely a db

    return dir or new_library_path is not None or app_context.config.rescan == RescanOption.ALWAYS


def enter_folder_context(ctx: Context, folder: str):
    if ctx.parent:
        raise RuntimeError("enter_folder_context called on subcontext")
    parent = copy(ctx)
    ctx.parent = parent
    ctx.config = copy(parent.config)
    ctx.config.library = Path(folder)
    require_library(ctx)
    logger.info(f"using in-memory context, library is {folder}")

    db = connection.open(connection.MEMORY)
    if ctx.click_ctx:
        ctx.click_ctx.call_on_close(lambda: connection.close(db))
    ctx.db = db
    ctx.select_albums = lambda _: selector.load_albums(db)
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


def _open_db_and_set_context_config(ctx: click.Context, app_context: Context, album_db_path: Path):
    logger.info(f"using database {str(album_db_path)}")
    db = connection.open(album_db_path)
    ctx.call_on_close(lambda: connection.close(db))
    app_context.config = db_config.load(db)
    return db


def _create_db_and_set_context_config(ctx: click.Context, app_context: Context, album_db_path: Path, new_library_path: Path | None):
    if app_context.console.is_interactive and not confirm(f"No database file found at {str(album_db_path)}. Create this file?"):
        raise SystemExit(1)

    os.makedirs(album_db_path.parent, exist_ok=True)
    db = _open_db_and_set_context_config(ctx, app_context, album_db_path)
    if new_library_path:
        app_context.config.library = new_library_path
        db_config.save(db, app_context.config)
    return db


def _ensure_library_dir(library_path: Path | None):
    if library_path is None:
        logger.error("No library path specified, use --library to initialize.")
        raise SystemExit(1)
    elif not library_path.is_dir():
        logger.error(f"Library must be a directory: {str(library_path)}")
        raise SystemExit(1)


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
