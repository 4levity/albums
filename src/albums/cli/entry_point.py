import rich.traceback
import rich_click as click

import albums

from .. import app
from .check import check
from .checks_ignore import checks_ignore
from .checks_notice import checks_notice
from .cli_context import DEFAULT_DB_LOCATION, pass_context, setup
from .click_custom import InvisibleCountParam
from .collections_add import collections_add
from .collections_remove import collections_remove
from .config import config
from .import_album import import_album
from .list_albums import list_albums
from .scan import scan
from .sql import sql
from .sync import sync

rich.traceback.install(show_locals=True, locals_max_string=150, locals_max_length=10)


@click.group(epilog=f"if --db-file is not specified, albums will use {DEFAULT_DB_LOCATION}")
@click.option("--collection", "-c", "collections", multiple=True, help="match collection name")
@click.option("--path", "-p", "paths", multiple=True, help="match album path within library")
@click.option("--dir", "-d", help="operate on a directory outside of the library")
@click.option("--regex", "-r", is_flag=True, help="enable regex match for album paths (default is exact path)")
@click.option("--library", help="specify path to music library (use when initializing database)")
@click.option("--db-file", help="specify path to albums.db (advanced)")
@click.option("--verbose", "-v", type=InvisibleCountParam(), count=True, help="enable verbose logging (-vv for more)")
@click.version_option(version=albums.__version__, message="%(prog)s version %(version)s")
@pass_context  # order of these decorators matters
@click.pass_context
def albums_group(
    ctx: click.Context,
    app_context: app.Context,
    collections: list[str],
    paths: list[str],
    dir: str,
    regex: bool,
    library: str,
    db_file: str,
    verbose: int,
):
    initial_scan = setup(ctx, app_context, verbose, collections, paths, dir, regex, library, db_file)

    if initial_scan:
        ctx.invoke(scan)


albums_group.add_command(check)
albums_group.add_command(collections_add)
albums_group.add_command(collections_remove)
albums_group.add_command(checks_ignore)
albums_group.add_command(checks_notice)
albums_group.add_command(config)
albums_group.add_command(import_album)
albums_group.add_command(list_albums)
albums_group.add_command(scan)
albums_group.add_command(sql)
albums_group.add_command(sync)
