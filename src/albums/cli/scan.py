import click
import logging
from pathlib import Path
import sqlite3
from .. import library


logger = logging.getLogger(__name__)


@click.command(help="scan and update database")
@click.option("--known-only", is_flag=True, help="only scan previously-scanned folders")
@click.pass_context
def scan(ctx: click.Context, known_only):
    if ctx.obj.get("SCAN_DONE", False):
        logger.info("scan already done, not scanning again")
        return

    db: sqlite3.Connection = ctx.obj["DB_CONNECTION"]
    albums: dict = ctx.obj["ALBUMS_CACHE"]
    library_root: Path = ctx.obj["LIBRARY_ROOT"]
    locations = ctx.obj["CONFIG"].get("locations", {})
    library.do_scan(db, albums, library_root, locations, known_only)
