"""CLI entry point: the root ``albums`` click group and its global options."""

import rich.traceback

import albums
import albums.cli.click_rich as click
from albums import app
from albums.database import Comparator
from albums.library import run_scan

from .check import check
from .checks_ignore import checks_ignore
from .checks_notice import checks_notice
from .cli_context import DEFAULT_DB_LOCATION, FilterCriteria, pass_context, setup
from .click_custom import InvisibleCountParam
from .collections_add import collections_add
from .collections_remove import collections_remove
from .collections_select import collections_select
from .config import config
from .import_command import import_command
from .init import init
from .list_albums import list_albums
from .scan import scan
from .sql import sql
from .sync import sync

rich.traceback.install(show_locals=True, locals_max_string=150, locals_max_length=10)


@click.group(epilog=f"if --db-file is not specified, albums will use {DEFAULT_DB_LOCATION}", add_help_option=False)
@click.option("--match", "-m", "matchers", metavar="K[op]V", multiple=True, help="filter key=value like -m path=Soundtracks/ or -m field:artist=Foo")  # pyright: ignore[reportUnknownMemberType]
@click.option("--invert", "-n", is_flag=True, help="invert match (return albums that DO NOT match)")  # pyright: ignore[reportUnknownMemberType]
@click.option("--collection", "-c", "collections", metavar="NAME", multiple=True, help="match collection name (same as -m collection=...)")  # pyright: ignore[reportUnknownMemberType]
@click.option("--path", "-p", "paths", metavar="PATH", multiple=True, help="match album path (same as -m path=...)")  # pyright: ignore[reportUnknownMemberType]
@click.option("--regex", "-r", is_flag=True, help="enable regex/partial match for -c and -p")  # pyright: ignore[reportUnknownMemberType]
@click.option("--dir", "-d", metavar="PATH", help="operate on a directory outside of the library")  # pyright: ignore[reportUnknownMemberType]
@click.option("--db-file", metavar="PATH", help="specify path to albums.db (advanced)")  # pyright: ignore[reportUnknownMemberType]
@click.option("--verbose", "-v", type=InvisibleCountParam(), count=True, help="enable verbose logging (-vv for more)")  # pyright: ignore[reportUnknownMemberType]
@click.help_option("--help", "-h", help="show this message and exit")  # pyright: ignore[reportUnknownMemberType]
@click.version_option(version=albums.__version__, message="%(prog)s version %(version)s", help="show the version number and exit")  # pyright: ignore[reportUnknownMemberType]
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
    invert: bool,
    db_file: str,
    verbose: int,
):
    """Manage a library of music albums: scan, check and fix tags, import albums, manage collections, and sync to players or storage."""
    default_cmp = Comparator.MATCH_REGEX if regex else Comparator.EQ
    filter_criteria = (
        [FilterCriteria("collection", c, default_cmp) for c in (collections or [])]
        + [FilterCriteria("path", p, default_cmp) for p in (paths or [])]
        + [FilterCriteria.from_expr(matcher) for matcher in matchers]
    )
    initial_scan = setup(ctx, app_context, verbose, filter_criteria, dir, invert, db_file)

    if initial_scan:
        run_scan(app_context)
        app_context.prescanned = True


albums_group.add_command(scan)
albums_group.add_command(list_albums)
albums_group.add_command(import_command)
albums_group.add_command(check)

albums_group.add_command(collections_add)
albums_group.add_command(collections_remove)
albums_group.add_command(collections_select)
albums_group.add_command(sync)

albums_group.add_command(checks_ignore)
albums_group.add_command(checks_notice)

albums_group.add_command(init)
albums_group.add_command(config)
albums_group.add_command(sql)
