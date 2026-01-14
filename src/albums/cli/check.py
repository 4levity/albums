import click
from ..library import checks


@click.command(help="report on metadata issues in selected albums")
@click.option("--default", is_flag=True, help="use default settings for all checks")
@click.pass_context
def check(ctx: click.Context, default: bool):
    check_config = ctx.obj["CONFIG"].get("checks")
    if default or not check_config:
        click.echo("using default check config")
        check_config = checks.ALL_CHECKS_DEFAULT

    issues = []
    for album in ctx.obj["SELECT_ALBUMS"](True):
        album_issues = checks.check(ctx.obj["DB_CONNECTION"], album, check_config)
        issues.extend([issue | {"path": album["path"]} for issue in album_issues])
    if len(issues) > 0:
        for issue in sorted(issues, key=lambda i: i["path"]):
            click.echo(f"{issue['message']} : {issue['path']}")
    else:
        click.echo("no exceptions found")
