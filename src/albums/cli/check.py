import click

from albums.library import scanner

from ..checks import all
from ..context import AppContext, pass_app_context


@click.command(help="report on metadata issues in selected albums")
@click.option("--default", is_flag=True, help="use default settings for all checks")
@click.option("--automatic", "-a", is_flag=True, help="perform automatic fixes")
@click.option("--interactive", "-i", is_flag=True, help="prompt for interactive repair")
@pass_app_context
def check(ctx: AppContext, default: bool, automatic: bool, interactive: bool):
    if default or "checks" not in ctx.config:
        click.echo("using default check config")
        ctx.config["checks"] = all.DEFAULT_CHECKS_CONFIG

    found = False
    for album_id, album_path, check_result in all.run_enabled(ctx):
        click.echo(f"{check_result.message} : {album_path}")
        if check_result.fixer is not None:
            rescan = False
            fixer = check_result.fixer
            if automatic and fixer.has_automatic:
                if check_result.fixer.automatic():
                    rescan = True
            if interactive and fixer.has_interactive:
                if check_result.fixer.interactive():
                    rescan = True
            if rescan:
                scanner.scan(ctx.db, ctx.library_root, ctx.config, lambda: [(album_path, album_id)], True)

        found = True
    if not found:
        click.echo("no exceptions found")
