import sqlite3
import click
import configparser
import logging
import os
from pathlib import Path

from ..tools import platform_dirs
from ..library import scanner
import albums.database.connection
import albums.database.selector


logger = logging.getLogger(__name__)


class AppContext(dict):  # must be a dict
    db: sqlite3.Connection
    config: dict
    library_root: Path
    _collections: list[str]
    _paths: list[str]
    _regex: bool

    def is_filtered(self):
        return len(self._collections) > 0 or len(self._paths) > 0

    def select_albums(self, load_track_tag: bool):
        return albums.database.selector.select_albums(self.db, self._collections, self._paths, self._regex, load_track_tag)

    def __init__(self, *args, **kwargs):
        # early setup?
        super(AppContext, self).__init__(*args, **kwargs)


pass_app_context = click.make_pass_decorator(AppContext, ensure=True)


def setup(ctx: click.Context, app_context: AppContext, collections: list[str], paths: list[str], regex: bool, config_file: str):
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

    if config.getboolean("options", "always_scan", fallback=False):
        ctx.invoke(scanner.scan)
