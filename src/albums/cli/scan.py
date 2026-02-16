import logging
from typing import Generator

import rich_click as click

from .. import app
from ..library import scanner
from ..types import RescanOption
from . import cli_context

logger = logging.getLogger(__name__)


@click.command(help="scan and update database")
@click.option("--reread", "-r", is_flag=True, help="reread tracks even if size/timestamp are unchanged")
@cli_context.pass_context
def scan(ctx: app.Context, reread: bool):
    if ctx.config.rescan == RescanOption.ALWAYS:
        ctx.console.print("scan already done, not scanning again")
        return

    def filtered_path_selector() -> Generator[tuple[str, int | None], None, None]:
        yield from ((album.path, album.album_id) for album in ctx.select_albums(False))

    scanner.scan(ctx, filtered_path_selector if ctx.is_filtered() else None, reread)
