import rich.traceback
import rich_click as click

import albums

from .. import app
from ..library import scanner
from .check import check
from .checks_ignore import checks_ignore
from .checks_notice import checks_notice
from .cli_context import DEFAULT_DB_LOCATION, pass_context, setup
from .click_custom import InvisibleCountParam
from .collections_add import collections_add
from .collections_remove import collections_remove
from .config import config
from .import_command import import_command
from .init import init
from .list_albums import list_albums
from .scan import scan
from .sql import sql
from .sync import sync

rich.traceback.install(show_locals=True, locals_max_string=150, locals_max_length=10)


@click.group(epilog=f"if --db-file is not specified, albums will use {DEFAULT_DB_LOCATION}")
@click.option("--match", "-m", "matchers", metavar="K=V", multiple=True, help="filter key=value like -m path=Soundtracks/ or -m tag=artist:Foo")
@click.option("--regex", "-r", is_flag=True, help="enable regex and partial matches")
@click.option("--collection", "-c", "collections", metavar="NAME", multiple=True, help="match collection name (same as -m collection=...)")
@click.option("--path", "-p", "paths", metavar="PATH", multiple=True, help="match album path (same as -m path=...)")
@click.option("--dir", "-d", metavar="PATH", help="operate on a directory outside of the library")
@click.option("--db-file", metavar="PATH", help="specify path to albums.db (advanced)")
@click.option("--verbose", "-v", type=InvisibleCountParam(), count=True, help="enable verbose logging (-vv for more)")
@click.version_option(version=albums.__version__, message="%(prog)s version %(version)s")
@pass_context  # order of these decorators matters
@click.pass_context
def albums_group(
    ctx: click.Context,
    app_context: app.Context,
    collections: list[str],
    paths: list[str],
    matchers: list[str],
    dir: str,
    regex: bool,
    db_file: str,
    verbose: int,
):
    if any(str.count(matcher, "=") < 1 for matcher in matchers):
        app_context.console.print('--match/-m options must be in the format "key=value"')

    matchers_list = (
        [("collection", c) for c in (collections or [])]
        + [("path", p) for p in (paths or [])]
        + [(kv[0], kv[1]) for kv in (matcher.split("=", 1) for matcher in matchers)]
    )
    initial_scan = setup(ctx, app_context, verbose, matchers_list, dir, regex, db_file)

    if initial_scan:
        scanner.scan(app_context)
        app_context.prescanned = True


albums_group.add_command(check)
albums_group.add_command(collections_add)
albums_group.add_command(collections_remove)
albums_group.add_command(checks_ignore)
albums_group.add_command(checks_notice)
albums_group.add_command(config)
albums_group.add_command(import_command)
albums_group.add_command(init)
albums_group.add_command(list_albums)
albums_group.add_command(scan)
albums_group.add_command(sql)
albums_group.add_command(sync)
