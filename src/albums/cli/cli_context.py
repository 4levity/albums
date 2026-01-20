import click
import configparser
import logging
import os
from pathlib import Path
from rich.logging import RichHandler

import albums.database.connection
from ..app import Context
from ..tools import platform_dirs


logger = logging.getLogger(__name__)


pass_context = click.make_pass_decorator(Context, ensure=True)


def setup(ctx: click.Context, app_context: Context, verbose: int, collections: list[str], paths: list[str], regex: bool, config_file: str):
    setup_logging(ctx, verbose)
    logger.info("starting albums")
    config = configparser.ConfigParser()
    config_files = [str(platform_dirs.site_config_path / "config.ini"), str(platform_dirs.user_config_path / "config.ini"), "config.ini"]
    if config_file:
        specified_config_path = Path(config_file)
        if specified_config_path.exists() and specified_config_path.is_file():
            config_files.append(config_file)
        else:
            logger.error(f"specified configuration file does not exist: {config_file}")
            ctx.abort()

    configs_read = config.read(config_files)
    if len(configs_read) > 0:
        logger.info(f"read config from: {configs_read}")
    else:
        logger.warning(f"no configuration file found! create one at one of these locations: {config_files}")

    if config.has_option("locations", "database"):
        album_db_file = config["locations"]["database"]
    else:
        album_db_file = str((platform_dirs.user_config_path / "albums.db"))
        logger.warning(f"no database file specified, using {album_db_file}")
        os.makedirs(platform_dirs.user_config_dir, exist_ok=True)

    db = albums.database.connection.open(album_db_file)
    ctx.call_on_close(lambda: albums.database.connection.close(db))

    app_context.db = db
    app_context.config = {section: dict(config.items(section)) for section in config.sections()}
    app_context.library_root = Path(config.get("locations", "library", fallback=str(Path.home() / "Music")))
    app_context._collections = collections
    app_context._paths = paths
    app_context._regex = regex


def setup_logging(ctx: Context, verbose: int):
    log_format = "%(message)s"
    rich = RichHandler(show_time=False, show_level=True, console=ctx.console)
    if verbose >= 2:
        logging.basicConfig(level=logging.DEBUG, format=log_format, handlers=[rich])
    elif verbose == 1:
        logging.basicConfig(level=logging.INFO, format=log_format, handlers=[rich])
    else:
        logging.basicConfig(level=logging.WARNING, format=log_format, handlers=[rich])
