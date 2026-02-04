import logging
import os
import tomllib
from pathlib import Path

import click
from platformdirs import PlatformDirs
from rich.logging import RichHandler
from rich.prompt import Confirm

import albums.database.connection
import albums.database.selector

from ..app import Context

logger = logging.getLogger(__name__)


pass_context = click.make_pass_decorator(Context, ensure=True)


PLATFORM_DIRS = PlatformDirs("albums", "4levity")
DEFAULT_CONFIG_FILE_LOCATIONS = [
    "config.toml",
    str(PLATFORM_DIRS.user_config_path / "config.toml"),
    str(PLATFORM_DIRS.site_config_path / "config.toml"),
]


def setup(ctx: click.Context, app_context: Context, verbose: int, collections: list[str], paths: list[str], regex: bool, config_file: str):
    app_context.click_ctx = ctx
    app_context.verbose = verbose
    setup_logging(app_context, verbose)
    logger.info("starting albums")

    config_path = None

    if config_file:  # use config file from command line, ignore others
        config_path = Path(config_file)
        if not config_path.exists() or not config_path.is_file():
            logger.error(f"specified configuration file does not exist: {config_file}")
            ctx.abort()
    else:  # use most-local configuration file from standard locations
        for f in DEFAULT_CONFIG_FILE_LOCATIONS:
            candidate = Path(f)
            if candidate.exists() and candidate.is_file():
                config_path = candidate
                break

    if config_path:
        with open(config_path, "rb") as file:
            app_context.config = tomllib.load(file)
        logger.info(f"read config from {config_path}")
    else:
        logger.info("no configuration file, using default configuration")
        app_context.config = {}

    app_context.library_root = Path(app_context.config.get("locations", {}).get("library", str(Path.home() / "Music")))
    if not app_context.library_root.is_dir():
        logger.error(f"library directory does not exist: {str(app_context.library_root)}")
        raise SystemExit(1)

    if "database" in app_context.config.get("locations", {}):
        album_db_file = app_context.config["locations"]["database"]
    else:
        album_db_file = str(PLATFORM_DIRS.user_config_path / "albums.db")
        logger.info(f"using default database location {album_db_file}")

    album_db_path = Path(album_db_file)
    if not album_db_path.exists():
        if app_context.console.is_interactive and not Confirm.ask(
            f"No database file found at {album_db_file}. Create this file?", console=app_context.console
        ):
            raise SystemExit(1)
        os.makedirs(album_db_path.parent, exist_ok=True)
        new_database = True
    else:
        new_database = False

    db = albums.database.connection.open(album_db_file)
    ctx.call_on_close(lambda: albums.database.connection.close(db))
    app_context.db = db
    app_context.select_albums = lambda load_track_tag: albums.database.selector.select_albums(db, collections, paths, regex, load_track_tag)

    # filters applied to command
    app_context.filter_collections = collections
    app_context.filter_paths = paths
    app_context.filter_regex = regex

    return new_database


def setup_logging(ctx: Context, verbose: int):
    log_format = "%(message)s"
    rich = RichHandler(show_time=False, show_level=True, console=ctx.console)
    if verbose >= 2:
        logging.basicConfig(level=logging.DEBUG, format=log_format, handlers=[rich])
    elif verbose == 1:
        logging.basicConfig(level=logging.INFO, format=log_format, handlers=[rich])
    else:
        logging.basicConfig(level=logging.WARNING, format=log_format, handlers=[rich])
