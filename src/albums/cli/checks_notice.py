import rich_click as click
from rich.prompt import Confirm

import albums.database.operations
from .. import app
from ..checks.all import ALL_CHECK_NAMES
from . import cli_context


@click.command("notice", help="selected albums stop ignoring specified checks")
@click.option("--force", "-f", is_flag=True, help="always skip confirmation")
@click.argument("check_names", nargs=-1)
@cli_context.pass_context
def checks_notice(ctx: app.Context, force: bool, check_names: list[str]):
    if not ctx.db:
        raise ValueError("notice requires database connection")

    for album in ctx.select_albums(False):
        changed = False
        error = False
        for target_check in check_names:
            if target_check not in ALL_CHECK_NAMES:
                ctx.console.print(f'"{target_check}" is not a valid check name. See [bold]albums check --help')
                error = True
            if target_check in album.ignore_checks:
                album.ignore_checks.remove(target_check)
                ctx.console.print(f"album {album.path} will stop ignoring {target_check}")
                changed = True
            elif ctx.is_filtered():  # don't show individual albums if operating on all albums (confirm below)
                ctx.console.print(f"album {album.path} will continue ignoring {target_check}")

        if changed and not error:
            if force or ctx.is_filtered() or Confirm.ask(f"stop ignoring checks {check_names} for all albums?", console=ctx.console):
                if album.album_id is None:
                    raise ValueError(f"unexpected album.album_id=None for {album.path}")
                albums.database.operations.update_ignore_checks(ctx.db, album.album_id, album.ignore_checks)
        elif error:
            ctx.console.print("changes not saved because some options were invalid")
