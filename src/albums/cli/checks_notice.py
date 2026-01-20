import rich_click as click
from rich.prompt import Confirm

import albums.database.operations
from .. import app
from . import cli_context


@click.command("notice", help="selected albums stop ignoring specified checks")
@click.option("--force", "-f", is_flag=True, help="always skip confirmation")
@click.argument("check_names", nargs=-1)
@cli_context.pass_context
def checks_notice(ctx: app.Context, force: bool, check_names: list[str]):
    if not force and not ctx.is_filtered() and not Confirm(f"stop ignoring checks {check_names} for all albums?", console=ctx.console):
        return

    for album in ctx.select_albums(False):
        changed = False
        for target_check in check_names:
            if target_check in album.ignore_checks:
                album.ignore_checks.remove(target_check)
                ctx.console.print(f"album {album.path} will stop ignoring {target_check}")
                changed = True
            elif ctx.is_filtered():
                ctx.console.print(f"album {album.path} will continue ignoring {target_check}")
        if changed:
            albums.database.operations.update_ignore_checks(ctx.db, album.album_id, album.ignore_checks)
