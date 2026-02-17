import logging
from pathlib import Path

import rich_click as click

from ..app import Context
from ..library import synchronizer
from ..types import RescanOption
from . import cli_context
from .scan import scan

logger = logging.getLogger(__name__)


@click.command("sync", help="sync selected albums with destination")
@click.argument("destination")
@click.option("--delete", is_flag=True, help="delete unrecognized paths in destination")
@click.option("--force", is_flag=True, help="skip confirmation when deleting files")
@cli_context.pass_context
def sync(ctx: Context, destination: str, delete: bool, force: bool):
    dest = Path(destination)
    if dest.exists() and dest.is_dir():
        if ctx.config.rescan == RescanOption.AUTO and ctx.click_ctx:
            ctx.click_ctx.invoke(scan)

        synchronizer.do_sync(ctx, ctx.select_albums(False), dest, delete, force)
    else:
        ctx.console.print("The sync destination must be a directory")
