import click
import logging
from pathlib import Path
from .. import synchronizer


logger = logging.getLogger(__name__)


@click.command("sync", help="sync selected albums with destination")
@click.argument("destination")
@click.option("--delete", is_flag=True, help="delete unrecognized paths in destination")
@click.option("--force", is_flag=True, help="skip confirmation when deleting files")
@click.pass_context
def sync(ctx: click.Context, destination, delete, force):
    dest = Path(destination)
    albums = ctx.obj["SELECT_ALBUMS"]()
    if not dest.exists() or not dest.is_dir():
        logger.error(f"not a directory: {dest}")
        return
    synchronizer.do_sync(albums, dest, ctx.obj["LIBRARY_ROOT"], delete, force)
