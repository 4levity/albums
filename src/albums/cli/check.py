import click
from .. import checks


@click.command(help="report on metadata issues in selected albums")
@click.pass_context
def check(ctx: click.Context):
    checks_enabled = ctx.obj["CONFIG"].get("checks", {})
    albums = ctx.obj["SELECT_ALBUMS"]()
    issues = []
    for album in albums:
        album_issues = checks.check(album, checks_enabled, ctx.obj["ALBUMS_CACHE"])
        issues.extend([issue | {"path": album["path"]} for issue in album_issues])
    if len(issues) > 0:
        for issue in sorted(issues, key=lambda i: i["path"]):
            click.echo(f"{issue['message']} : {issue['path']}")
    else:
        click.echo("no exceptions found")
