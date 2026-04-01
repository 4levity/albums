import logging
from pathlib import Path

import rich_click as click

from ..app import Context
from ..config import RescanOption, SyncDestination
from ..library import scanner, synchronizer
from .cli_context import pass_context, require_configured, require_library, require_persistent_context

logger = logging.getLogger(__name__)


@click.command("sync", help="sync selected albums with destination", add_help_option=False)
@click.argument("destination")
@click.option("--delete", is_flag=True, help="delete unrecognized paths in destination")
@click.option("--force", is_flag=True, help="skip confirmation when deleting files")
@click.help_option("--help", "-h", help="show this message and exit")
@pass_context
def sync(ctx: Context, destination: str, delete: bool, force: bool):
    require_configured(ctx)
    require_persistent_context(ctx)
    require_library(ctx)
    path_root = Path(destination)
    if path_root.exists() and path_root.is_dir():
        if ctx.config.rescan == RescanOption.AUTO:
            scanner.scan(ctx)

        synchronizer.do_sync(ctx, SyncDestination("", path_root), delete, force)
    else:
        ctx.console.print("The sync destination must be a directory")
