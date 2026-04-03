import logging
import platform
from pathlib import Path

import rich_click as click
from prompt_toolkit import choice

from ..app import Context
from ..config import RescanOption, SyncDestination
from ..library.scanner import scan
from ..library.synchronizer import Synchronizer
from .cli_context import pass_context, require_configured, require_library, require_persistent_context

logger = logging.getLogger(__name__)


@click.command(
    "sync",
    help="sync albums with destination",
    epilog="DESTINATION can be any path, or use the path / collection name of a configured sync destination",
    add_help_option=False,
)
@click.argument("destination", required=False)
@click.option("--delete", "-d", is_flag=True, help="delete unrecognized paths in destination")
@click.option("--force", "-f", is_flag=True, help="skip confirmation when deleting files")
@click.help_option("--help", "-h", help="show this message and exit")
@pass_context
def sync(ctx: Context, destination: str, delete: bool, force: bool):
    require_configured(ctx)
    require_persistent_context(ctx)
    require_library(ctx)

    sync_destinations = [
        sync_destination
        for sync_destination in ctx.config.sync_destinations
        if destination in [sync_destination.collection, str(sync_destination.path_root)]
    ]

    confirm = False
    if ctx.is_filtered:
        if not destination:
            ctx.console.print("To sync a dynamically filtered set of albums, specify the destination directory.")
            raise SystemExit(1)
        if sync_destinations:
            ctx.console.print("To sync a pre-configured destination, do not specify any album filters.")
            raise SystemExit(1)
        dest_path = Path(destination)
        if not dest_path.is_absolute():
            ctx.console.print(f"The destination path must {'include the drive letter' if platform.system() == 'Windows' else 'be absolute'}.")
            raise SystemExit(1)
        if not dest_path.exists():
            ctx.console.print("The destination path must exist.")
            raise SystemExit(1)
        if not dest_path.is_dir():
            ctx.console.print("[bold]Error:[/bold] destination path is not a directory.")
            raise SystemExit(1)

        sync_destinations = [SyncDestination("", dest_path)]
    else:
        if not destination:
            sync_destinations = ctx.config.sync_destinations
            confirm = True
        elif not sync_destinations:
            ctx.console.print("Either specify a pre-configured sync destination, or specify filter option(s) to select which albums to sync.")
            raise SystemExit(1)

    if confirm or len(sync_destinations) > 1:
        ix = choice(
            message="Select a pre-configured sync destination",
            options=[(ix, str(dest)) for ix, dest in enumerate(sorted(sync_destinations))],
        )
        dest = sync_destinations[ix]
    else:
        dest = sync_destinations[0]

    if ctx.config.rescan == RescanOption.AUTO:
        ctx.console.print("Scanning library before sync (see config settings.rescan to disable this)")
        scan(ctx)

    Synchronizer(ctx, dest).do_sync(delete, force)
