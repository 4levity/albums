import click

from .. import app
import albums.database.operations


@click.command("ignore", help="ignore certain checks for specified albums")
@click.option("--force", "-f", is_flag=True, help="always skip confirmation")
@click.argument("check_names", nargs=-1)
@app.pass_context
def checks_ignore(ctx: app.Context, force: bool, check_names: list[str]):
    if not force and not ctx.is_filtered() and not click.confirm(f"ignore checks {check_names} for all albums?"):
        return

    for album in ctx.select_albums(False):
        changed = False
        for target_check in check_names:
            if target_check in album.ignore_checks:
                click.echo(f"album {album.path} is already configured to ignore {target_check}")
            else:
                album.ignore_checks.append(target_check)
                click.echo(f"album {album.path} will ignore {target_check}")
                changed = True
        if changed:
            albums.database.operations.update_ignore_checks(ctx.db, album.album_id, album.ignore_checks)
