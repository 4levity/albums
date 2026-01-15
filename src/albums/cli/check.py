import click

from ..checks import defaults, all
from ..context import AppContext, pass_app_context


@click.command(help="report on metadata issues in selected albums")
@click.option("--default", is_flag=True, help="use default settings for all checks")
@pass_app_context
def check(ctx: AppContext, default: bool):
    if default or "checks" not in ctx.config:
        click.echo("using default check config")
        ctx.config["checks"] = defaults.ALL_CHECKS_DEFAULT

    found = False
    for album_path, check_result in all.run_enabled(ctx):
        click.echo(f"{check_result.message} : {album_path}")
        found = True
    if not found:
        click.echo("no exceptions found")
