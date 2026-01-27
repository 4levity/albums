import rich_click as click
import rich.traceback

from .. import app
from . import cli_context
from .collections_add import collections_add
from .collections_remove import collections_remove
from .checks_ignore import checks_ignore
from .checks_notice import checks_notice
from .check import check
from .list_albums import list_albums
from .scan import scan
from .sql import sql
from .sync import sync


rich.traceback.install(show_locals=True)


@click.group(
    epilog=f"if --config-file is not specified, albums will search for config files in these locations: {', '.join(cli_context.DEFAULT_CONFIG_FILE_LOCATIONS)}"
)
@click.option("--collection", "-c", "collections", multiple=True, help="match collection name")
@click.option("--path", "-p", "paths", multiple=True, help="match album path within library")
@click.option("--regex", "-r", is_flag=True, help="enable regex match for album paths (default is exact path)")
@click.option("--config-file", help="specify path to config.toml")
@click.option("--verbose", "-v", count=True, help="enable verbose logging (-vv for more)")
@cli_context.pass_context  # order of these decorators matters
@click.pass_context
def albums(ctx: click.Context, app_context: app.Context, collections: list[str], paths: list[str], regex: bool, config_file: str, verbose: int):
    new_database = cli_context.setup(ctx, app_context, verbose, collections, paths, regex, config_file)

    rescan = app_context.config.get("options", {}).get("rescan", "auto")
    VALID_RESCAN_OPTIONS = ["always", "auto", "never"]
    if rescan not in VALID_RESCAN_OPTIONS:
        app_context.console.print(f"configuration option rescan must be one of {', '.join(VALID_RESCAN_OPTIONS)}")
        raise SystemExit(1)
    app_context.rescan_auto = rescan == "auto"
    if rescan == "always" or (rescan == "auto" and new_database):
        ctx.invoke(scan)


albums.add_command(check)
albums.add_command(collections_add)
albums.add_command(collections_remove)
albums.add_command(checks_ignore)
albums.add_command(checks_notice)
albums.add_command(list_albums)
albums.add_command(scan)
albums.add_command(sql)
albums.add_command(sync)
