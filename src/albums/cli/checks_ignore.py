import rich_click as click
from prompt_toolkit.shortcuts import confirm
from sqlalchemy.orm import Session

from ..app import Context
from ..checks.all import ALL_CHECK_NAMES
from ..checks.helpers import album_display_name
from .cli_context import pass_context, require_persistent_context


@click.command("ignore", help="ignore certain checks for specified albums")
@click.option("--force", "-f", is_flag=True, help="always skip confirmation")
@click.argument("check_names", nargs=-1)
@pass_context
def checks_ignore(ctx: Context, force: bool, check_names: list[str]):
    require_persistent_context(ctx)
    with Session(ctx.db) as session:
        for album in ctx.select_album_entities(session):
            changed = False
            error = False
            for target_check in check_names:
                if target_check not in ALL_CHECK_NAMES:
                    ctx.console.print(f'"{target_check}" is not a valid check name. See [bold]albums check --help')
                    error = True
                if target_check in album.ignore_checks:
                    ctx.console.print(f"album {album_display_name(ctx, album)} is already configured to ignore {target_check}")
                else:
                    album.ignore_checks.append(target_check)
                    changed = True
                    if ctx.is_filtered:  # don't show individual albums if operating on all albums (confirm below)
                        ctx.console.print(f"album {album_display_name(ctx, album)} - ignore {target_check}")

            if changed and not error:
                if force or ctx.is_filtered or confirm(f"ignore checks {check_names} for all albums?"):
                    session.commit()
            elif error:
                ctx.console.print("changes not saved because some options were invalid")
