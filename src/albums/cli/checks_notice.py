import click

import albums.database.operations
from .. import app


@click.command("notice", help="selected albums stop ignoring specified checks")
@click.option("--force", "-f", is_flag=True, help="always skip confirmation")
@click.argument("check_names", nargs=-1)
@app.pass_context
def checks_notice(ctx: app.Context, force: bool, check_names: list[str]):
    if not force and not ctx.is_filtered() and not click.confirm(f"stop ignoring checks {check_names} for all albums?"):
        return

    for album in ctx.select_albums(False):
        changed = False
        for target_check in check_names:
            if target_check in album.ignore_checks:
                album.ignore_checks.remove(target_check)
                click.echo(f"album {album.path} will stop ignoring {target_check}")
                changed = True
            elif ctx.is_filtered():
                click.echo(f"album {album.path} will continue ignoring {target_check}")
        if changed:
            albums.database.operations.update_ignore_checks(ctx.db, album.album_id, album.ignore_checks)
