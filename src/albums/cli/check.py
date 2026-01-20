import rich_click as click

from .. import app
from ..checks import all
from ..checks.base_fixer import prompt_ignore_checks
from ..library import scanner
from . import cli_context


@click.command(
    help="report on metadata issues in selected albums",
    epilog=f"If any CHECK_NAMES are provided, only those checks will run. Valid checks are: {', '.join(all.ALL_CHECK_NAMES)}",
)
@click.option("--default", is_flag=True, help="use default settings for all checks")
@click.option("--automatic", "-a", is_flag=True, help="perform automatic fixes")
@click.option("--interactive", "-i", is_flag=True, help="prompt if interactive fix is available")
@click.option("--prompt-always", "-P", is_flag=True, help="prompt even when only option is ignore")
@click.argument("check_names", nargs=-1)
@cli_context.pass_context
def check(ctx: app.Context, default: bool, automatic: bool, interactive: bool, prompt_always: bool, check_names: list[str]):
    if default or "checks" not in ctx.config:
        ctx.console.print("using default check config")
        ctx.config["checks"] = all.DEFAULT_CHECKS_CONFIG

    if len(check_names) > 0:
        # ensure check names are valid and configuration is present
        for check_name in check_names:
            if check_name not in all.ALL_CHECK_NAMES:
                ctx.console.print(f"invalid check name: {check_name}")
                return
            if check_name not in ctx.config["checks"]:
                ctx.config["checks"][check_name] = all.DEFAULT_CHECKS_CONFIG[check_name]
        # enable only specified checks
        for check_name in ctx.config["checks"].keys():
            ctx.config["checks"][check_name]["enabled"] = check_name in check_names

    found = False
    for album, check_result in all.run_enabled(ctx):
        ctx.console.print(f"{check_result.message} : {album.path}")
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
                scanner.scan(ctx, lambda: [(album.path, album.album_id)], True)
        elif prompt_always:
            ctx.console.print("No fix available. ", end="")
            prompt_ignore_checks(ctx, album, check_result.name)

        found = True
    if not found:
        ctx.console.print("no exceptions found")
