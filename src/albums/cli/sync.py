import rich_click as click
import logging
from pathlib import Path

from .. import app
from ..library import synchronizer
from . import cli_context


logger = logging.getLogger(__name__)


@click.command("sync", help="sync selected albums with destination")
@click.argument("destination")
@click.option("--delete", is_flag=True, help="delete unrecognized paths in destination")
@click.option("--force", is_flag=True, help="skip confirmation when deleting files")
@cli_context.pass_context
def sync(ctx: app.Context, destination, delete, force):
    dest = Path(destination)
    if dest.exists() and dest.is_dir():
        synchronizer.do_sync(ctx, ctx.select_albums(False), dest, delete, force)
    else:
        ctx.console.print("The sync destination must be a directory")
