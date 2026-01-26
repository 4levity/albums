from rich.markup import escape
import rich_click as click

from .. import app
from ..checks import all
from ..checks.interact import interact
from ..library import scanner
from . import cli_context


@click.command(
    help="report on metadata issues in selected albums",
    epilog=f"If any CHECK_NAMES are provided, only those checks will run. Valid checks are: {', '.join(all.ALL_CHECK_NAMES)}",
)
@click.option("--default", is_flag=True, help="use default settings for all checks")
@click.option("--automatic", "-a", is_flag=True, help="if there is an automatic fix, do it WITHOUT ASKING")
@click.option("--fix", "-f", is_flag=True, help="prompt when there is a selectable fix available")
@click.option("--interactive", "-i", is_flag=True, help="ask what to do even if the only options are manual (implies -f)")
@click.argument("check_names", nargs=-1)
@cli_context.pass_context
def check(ctx: app.Context, default: bool, automatic: bool, fix: bool, interactive: bool, check_names: list[str]):
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
    for album, check, check_result in all.run_enabled(ctx):
        fixer = check_result.fixer
        if automatic and fixer and fixer.option_automatic_index is not None:
            ctx.console.print(f'[bold]automatically fixing:[/bold] {escape(check_result.message)} : "{escape(album.path)}"')
            rescan = fixer.fix(fixer.options[fixer.option_automatic_index])
        elif interactive or (fixer and fix):
            ctx.console.print(f'>> "{album.path}"', markup=False)
            rescan = interact(ctx, check.name, check_result, album)
        else:
            ctx.console.print(f'{check_result.message} : "{album.path}"', markup=False)
            rescan = False

        if rescan:
            scanner.scan(ctx, lambda: [(album.path, album.album_id)], True)

        found = True
    if not found:
        ctx.console.print("no exceptions found")
