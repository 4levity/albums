#!/usr/bin/env python


import os
import click
import configparser
import logging
from pathlib import Path
from albums import actions, database, library, selector, synchronizer, tools


logger = logging.getLogger(__name__)


@click.group()
@click.option("--collection", "-c", "collections", multiple=True, help="match collection name")
@click.option("--path", "-p", "paths", multiple=True, help="match album path within library")
@click.option("--match", "-m", type=click.Choice(selector.MatchType, case_sensitive=False), default="EXACT", help="type of match for album paths")
@click.option("--config-file", help="specify path to config.ini")
@click.option("--verbose", "-v", count=True, help="enable verbose logging (-vv for more)")
@click.pass_context
def albums(ctx: click.Context, collections: list[str], paths: list[str], match: selector.MatchType, config_file: str, verbose: int):
    tools.setup_logging(verbose)
    logger.info("starting albums")

    config = configparser.ConfigParser()
    config_files = [str(tools.platform_dirs.site_config_path / "config.ini"), str(tools.platform_dirs.user_config_path / "config.ini"), "config.ini"]
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
        album_db_file = str((tools.platform_dirs.user_config_path / "albums.db"))
        logger.warning(f"no database file specified, using {album_db_file}")
        os.makedirs(tools.platform_dirs.user_config_dir, exist_ok=True)

    db = database.open(album_db_file)
    ctx.call_on_close(lambda: database.close(db))
    ctx.ensure_object(dict)

    # load the entire database - currently the cache is scanned by every command
    albums_cache = database.load(db)
    logger.info(f"loaded info for {len(albums_cache)} albums from {album_db_file}")
    ctx.obj["ALBUMS_CACHE"] = albums_cache
    ctx.obj["CONFIG"] = {section: dict(config.items(section)) for section in config.sections()}
    ctx.obj["DB_CONNECTION"] = db
    ctx.obj["LIBRARY_ROOT"] = Path(config.get("locations", "library", fallback=str(Path.home() / "Music")))
    ctx.obj["SELECT_ALBUMS"] = lambda: selector.select_albums(albums_cache, paths, collections, match)

    if config.getboolean("options", "always_scan", fallback=False):
        ctx.invoke(library.scan)
        ctx.obj["SCAN_DONE"] = True


albums.add_command(actions.list_albums)
albums.add_command(actions.check)
albums.add_command(actions.add_to_collections)
albums.add_command(actions.remove_from_collections)
albums.add_command(library.scan)
albums.add_command(synchronizer.sync)


if __name__ == "__main__":
    albums()
