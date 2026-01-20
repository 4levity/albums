import rich_click as click
import logging

from .. import app
from ..library import scanner
from . import cli_context


logger = logging.getLogger(__name__)


@click.command(help="scan and update database")
@click.option("--reread", "-r", is_flag=True, help="reread tracks even if size/timestamp are unchanged")
@cli_context.pass_context
def scan(ctx: app.Context, reread: bool):
    if str.lower(ctx.config.get("options", {}).get("always_scan", "false")) != "false":
        ctx.console.print("scan already done, not scanning again")
        return

    def filtered_path_selector():
        yield from ((album.path, album.album_id) for album in ctx.select_albums(False))

    scanner.scan(ctx.db, ctx.library_root, ctx.config, filtered_path_selector if ctx.is_filtered() else None, reread)
