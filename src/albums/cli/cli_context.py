import logging
import os
import shutil
from pathlib import Path

import click
from platformdirs import PlatformDirs
from rich.logging import RichHandler
from rich.prompt import Confirm

from ..app import Context
from ..database import configuration, connection, selector

logger = logging.getLogger(__name__)


pass_context = click.make_pass_decorator(Context, ensure=True)


PLATFORM_DIRS = PlatformDirs("albums", "4levity")
DEFAULT_DB_LOCATION = str(PLATFORM_DIRS.user_config_path / "albums.db")


def setup(
    ctx: click.Context,
    app_context: Context,
    verbose: int,
    collections: list[str],
    paths: list[str],
    regex: bool,
    new_library: str | None,
    db_file: str | None,
):
    app_context.click_ctx = ctx
    app_context.verbose = verbose
    setup_logging(app_context, verbose)
    logger.info("starting albums")

    album_db_file = db_file if db_file is not None else os.environ.get("ALBUMS_DB")
    if album_db_file is None:
        if Path("albums.db").is_file():
            album_db_file = "albums.db"
    if album_db_file is None:
        album_db_file = DEFAULT_DB_LOCATION
    album_db_path = Path(album_db_file)
    new_library_path: Path | None = None
    if not album_db_path.exists():
        if new_library:
            path = Path(new_library)
            if path.is_dir():
                new_library_path = path
            else:
                app_context.console.print(f"Must be a directory: {new_library}")
        else:
            if PLATFORM_DIRS.user_music_path.is_dir():
                if Confirm.ask(
                    f"No library path specifed with --library, do you want to use {str(PLATFORM_DIRS.user_music_path)} ?", console=app_context.console
                ):
                    new_library_path = PLATFORM_DIRS.user_music_path
        if not new_library_path:
            logger.error("No library specifed, use --library option")
            raise SystemExit(1)

        if app_context.console.is_interactive and not Confirm.ask(
            f"No database file found at {album_db_file}. Create this file?", console=app_context.console
        ):
            raise SystemExit(1)
        os.makedirs(album_db_path.parent, exist_ok=True)
        new_database = True
    else:
        if new_library:
            logger.error("the --library option may only be used when creating a database")
            raise SystemExit(1)
        new_database = False

    logger.info(f"using database {album_db_file}")
    db = connection.open(album_db_file)
    ctx.call_on_close(lambda: connection.close(db))
    app_context.config = configuration.load(db)
    if new_library_path:
        app_context.config.library = new_library_path
        configuration.save(db, app_context.config)

    if not app_context.config.library.is_dir():
        logger.error(f"library directory does not exist: {str(app_context.config.library)}")
        raise SystemExit(1)

    if app_context.config.tagger:
        if not shutil.which(app_context.config.tagger):
            logger.warning(f'configuration specifies a tagger program "{app_context.config.tagger}" but it does not seem to be on the path')
    elif shutil.which("easytag"):  # could look for others too
        app_context.config.tagger = "easytag"

    app_context.db = db
    app_context.select_albums = lambda load_track_tag: selector.select_albums(db, collections, paths, regex, load_track_tag)

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
    logging.captureWarnings(True)
