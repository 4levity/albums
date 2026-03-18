import logging
from pathlib import Path

import rich_click as click

from ..app import Context
from ..config import RescanOption
from ..library import scanner, synchronizer
from .cli_context import pass_context, require_database, require_library, require_persistent_context

logger = logging.getLogger(__name__)


@click.command("sync", help="sync selected albums with destination")
@click.argument("destination")
@click.option("--delete", is_flag=True, help="delete unrecognized paths in destination")
@click.option("--force", is_flag=True, help="skip confirmation when deleting files")
@pass_context
def sync(ctx: Context, destination: str, delete: bool, force: bool):
    require_persistent_context(ctx, "sync")
    require_database(ctx, "sync")
    require_library(ctx, "sync")
    dest = Path(destination)
    if dest.exists() and dest.is_dir():
        if ctx.config.rescan == RescanOption.AUTO:
            scanner.scan(ctx)

        synchronizer.do_sync(ctx, dest, delete, force)
    else:
        ctx.console.print("The sync destination must be a directory")
