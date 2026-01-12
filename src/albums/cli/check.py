import click
from .. import checks


@click.command(help="report on metadata issues in selected albums")
@click.pass_context
def check(ctx: click.Context):
    checks_enabled = ctx.obj["CONFIG"].get("checks", {})
    issues = []
    for album in ctx.obj["SELECT_ALBUMS"]():
        album_issues = checks.check(ctx.obj["DB_CONNECTION"], album, checks_enabled)
        issues.extend([issue | {"path": album["path"]} for issue in album_issues])
    if len(issues) > 0:
        for issue in sorted(issues, key=lambda i: i["path"]):
            click.echo(f"{issue['message']} : {issue['path']}")
    else:
        click.echo("no exceptions found")
