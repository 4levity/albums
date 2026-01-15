import click
from ..library import checks
from .context import AppContext, pass_app_context


@click.command(help="report on metadata issues in selected albums")
@click.option("--default", is_flag=True, help="use default settings for all checks")
@pass_app_context
def check(ctx: AppContext, default: bool):
    check_config = ctx.config.get("checks")
    if default or not check_config:
        click.echo("using default check config")
        check_config = checks.ALL_CHECKS_DEFAULT

    issues = []
    for album in ctx.select_albums(True):
        album_issues = checks.check(ctx.db, album, check_config)
        issues.extend([issue | {"path": album.path} for issue in album_issues])
    if len(issues) > 0:
        for issue in sorted(issues, key=lambda i: i["path"]):
            click.echo(f"{issue['message']} : {issue['path']}")
    else:
        click.echo("no exceptions found")
