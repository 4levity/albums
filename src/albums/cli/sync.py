import click
import logging
from pathlib import Path

from ..library import synchronizer


logger = logging.getLogger(__name__)


@click.command("sync", help="sync selected albums with destination")
@click.argument("destination")
@click.option("--delete", is_flag=True, help="delete unrecognized paths in destination")
@click.option("--force", is_flag=True, help="skip confirmation when deleting files")
@click.pass_context
def sync(ctx: click.Context, destination, delete, force):
    dest = Path(destination)
    if dest.exists() and dest.is_dir():
        synchronizer.do_sync(ctx.obj["SELECT_ALBUMS"](False), dest, ctx.obj["LIBRARY_ROOT"], delete, force)
    else:
        click.echo("The sync destination must be a directory")
        ctx.abort()
