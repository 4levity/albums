import rich_click as click
from rich.prompt import Confirm

from .. import app
from ..checks.all import ALL_CHECK_NAMES
from ..database import operations
from . import cli_context


@click.command("ignore", help="ignore certain checks for specified albums")
@click.option("--force", "-f", is_flag=True, help="always skip confirmation")
@click.argument("check_names", nargs=-1)
@cli_context.pass_context
def checks_ignore(ctx: app.Context, force: bool, check_names: list[str]):
    if not ctx.db:
        raise ValueError("ignore requires database connection")

    for album in ctx.select_albums(False):
        changed = False
        error = False
        for target_check in check_names:
            if target_check not in ALL_CHECK_NAMES:
                ctx.console.print(f'"{target_check}" is not a valid check name. See [bold]albums check --help')
                error = True
            if target_check in album.ignore_checks:
                ctx.console.print(f"album {album.path} is already configured to ignore {target_check}", markup=False)
            else:
                album.ignore_checks.append(target_check)
                changed = True
                if ctx.is_filtered():  # don't show individual albums if operating on all albums (confirm below)
                    ctx.console.print(f"album {album.path} - ignore {target_check}", markup=False)

        if changed and not error:
            if album.album_id is None:
                raise ValueError(f"cannot ignore checks for album with no album_id: {album.path}")
            if force or ctx.is_filtered() or Confirm.ask(f"ignore checks {check_names} for all albums?", console=ctx.console):
                operations.update_ignore_checks(ctx.db, album.album_id, album.ignore_checks)
        elif error:
            ctx.console.print("changes not saved because some options were invalid")
