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


def setup(ctx: click.Context, collections: list[str], paths: list[str], regex: bool, config_file: str):
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
    ctx.ensure_object(dict)

    ctx.obj["CONFIG"] = {section: dict(config.items(section)) for section in config.sections()}
    ctx.obj["DB_CONNECTION"] = db
    ctx.obj["LIBRARY_ROOT"] = Path(config.get("locations", "library", fallback=str(Path.home() / "Music")))
    ctx.obj["SELECT_ALBUMS"] = lambda load_track_tag: albums.database.selector.select_albums(db, collections, paths, regex, load_track_tag)

    if config.getboolean("options", "always_scan", fallback=False):
        ctx.invoke(scanner.scan)
        ctx.obj["SCAN_DONE"] = True
