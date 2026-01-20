import rich_click as click
import rich.traceback

from .. import app
from ..library import scanner
from . import cli_context
from .collections_add import collections_add
from .collections_remove import collections_remove
from .checks_ignore import checks_ignore
from .checks_notice import checks_notice
from .check import check
from .list_albums import list_albums
from .scan import scan
from .sync import sync


rich.traceback.install(show_locals=True)


@click.group()
@click.option("--collection", "-c", "collections", multiple=True, help="match collection name")
@click.option("--path", "-p", "paths", multiple=True, help="match album path within library")
@click.option("--regex", "-r", is_flag=True, help="type of match for album paths")
@click.option("--config-file", help="specify path to config.ini")
@click.option("--verbose", "-v", count=True, help="enable verbose logging (-vv for more)")
@cli_context.pass_context  # order of these decorators matters
@click.pass_context
def albums(ctx: click.Context, app_context: app.Context, collections: list[str], paths: list[str], regex: bool, config_file: str, verbose: int):
    cli_context.setup(ctx, app_context, verbose, collections, paths, regex, config_file)

    if app_context.config.get("options", {}).get("always_scan", "false") != "false":
        ctx.invoke(scanner.scan)


albums.add_command(check)
albums.add_command(collections_add)
albums.add_command(collections_remove)
albums.add_command(checks_ignore)
albums.add_command(checks_notice)
albums.add_command(list_albums)
albums.add_command(scan)
albums.add_command(sync)
