import click


from .. import app
from ..checks import all
from ..checks.base_fixer import prompt_ignore_checks
from ..library import scanner


@click.command(help="report on metadata issues in selected albums")
@click.option("--default", is_flag=True, help="use default settings for all checks")
@click.option("--automatic", "-a", is_flag=True, help="perform automatic fixes")
@click.option("--interactive", "-i", is_flag=True, help="prompt if interactive fix is available")
@click.option("--prompt-always", "-P", is_flag=True, help="prompt even when only option is ignore")
@app.pass_context
def check(ctx: app.Context, default: bool, automatic: bool, interactive: bool, prompt_always: bool):
    if default or "checks" not in ctx.config:
        click.echo("using default check config")
        ctx.config["checks"] = all.DEFAULT_CHECKS_CONFIG

    found = False
    for album, check_result in all.run_enabled(ctx):
        click.echo(f"{check_result.message} : {album.path}")
        if check_result.fixer is not None:
            rescan = False
            fixer = check_result.fixer
            if automatic and fixer.has_automatic:
                if check_result.fixer.automatic():
                    rescan = True
            if prompt_always or (interactive and fixer.has_interactive):
                if check_result.fixer.interact():
                    rescan = True
            if rescan:
                scanner.scan(ctx.db, ctx.library_root, ctx.config, lambda: [(album.path, album.album_id)], True)
        elif prompt_always:
            click.echo("No fix available. ", nl=False)
            prompt_ignore_checks(ctx.db, album, check_result.name)

        found = True
    if not found:
        click.echo("no exceptions found")
