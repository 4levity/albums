import rich_click as click

from .. import app
from ..checks import all
from ..checks.checker import run_enabled
from . import cli_context


@click.command(
    help="report and sometimes fix issues in selected albums",
    epilog=f"If CHECKS are provided, those checks (only) will be enabled. Valid CHECKS are: {', '.join(all.ALL_CHECK_NAMES)}",
)
@click.option("--default", is_flag=True, help="use default settings for all checks, including whether they are enabled")
@click.option("--automatic", "-a", is_flag=True, help="if there is an automatic fix, do it WITHOUT ASKING")
@click.option("--preview", "-p", is_flag=True, help="preview the automatic fixes that would be made with -a")
@click.option("--fix", "-f", is_flag=True, help="prompt when there is a selectable fix available")
@click.option("--interactive", "-i", is_flag=True, help="ask what to do even if the only options are manual (implies -f)")
@click.argument("checks", nargs=-1)
@cli_context.pass_context
def check(ctx: app.Context, default: bool, automatic: bool, preview: bool, fix: bool, interactive: bool, checks: list[str]):
    if interactive and automatic:
        ctx.console.print("cannot use --interactive with --automatic")
        raise SystemExit(1)
    if preview and (automatic or fix or interactive):
        ctx.console.print("--preview cannot be used with other fix options")
        raise SystemExit(1)

    if default or "checks" not in ctx.config:
        ctx.console.print("using default check config")
        ctx.config["checks"] = all.DEFAULT_CHECKS_CONFIG

    if len(checks) > 0:
        # validate check names
        for check_name in checks:
            if check_name not in all.ALL_CHECK_NAMES:
                ctx.console.print(f"invalid check name: {check_name}")
                return
            # use default if no configuration present
            if check_name not in ctx.config["checks"]:
                ctx.config["checks"][check_name] = all.DEFAULT_CHECKS_CONFIG[check_name]
        # enable only specified checks
        for check_name in ctx.config["checks"].keys():
            ctx.config["checks"][check_name]["enabled"] = check_name in checks

    issues = run_enabled(ctx, automatic, preview, fix, interactive)
    if issues == 0:
        ctx.console.print("no exceptions found")
