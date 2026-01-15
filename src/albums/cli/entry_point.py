import click

from .. import context
from ..library import scanner
from ..tools import setup_logging
from .add_to_collections import add_to_collections
from .check import check
from .list_albums import list_albums
from .remove_from_collections import remove_from_collections
from .scan import scan
from .sync import sync


@click.group()
@click.option("--collection", "-c", "collections", multiple=True, help="match collection name")
@click.option("--path", "-p", "paths", multiple=True, help="match album path within library")
@click.option("--regex", "-r", is_flag=True, help="type of match for album paths")
@click.option("--config-file", help="specify path to config.ini")
@click.option("--verbose", "-v", count=True, help="enable verbose logging (-vv for more)")
@context.pass_app_context  # order of these decorators matters
@click.pass_context
def albums(
    ctx: click.Context, app_context: context.AppContext, collections: list[str], paths: list[str], regex: bool, config_file: str, verbose: int
):
    setup_logging(verbose)
    context.setup(ctx, app_context, collections, paths, regex, config_file)

    if app_context.config.get("options", {}).get("always_scan", "false") != "false":
        ctx.invoke(scanner.scan)


albums.add_command(add_to_collections)
albums.add_command(check)
albums.add_command(list_albums)
albums.add_command(remove_from_collections)
albums.add_command(scan)
albums.add_command(sync)
