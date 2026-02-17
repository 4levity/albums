import rich_click as click

from ..app import Context
from ..checks.all import ALL_CHECK_NAMES
from ..checks.checker import required_disabled_checks, run_enabled
from ..types import RescanOption, default_checks_config
from . import cli_context
from .scan import scan


@click.command(
    help="report and sometimes fix issues in selected albums",
    epilog=f"If CHECKS are provided, those checks (only) will be enabled. Valid CHECKS are: {', '.join(sorted(ALL_CHECK_NAMES))}",
)
@click.option("--default", is_flag=True, help="use default settings for all checks, including whether they are enabled")
@click.option("--automatic", "-a", is_flag=True, help="if there is an automatic fix, do it WITHOUT ASKING")
@click.option("--preview", "-p", is_flag=True, help="preview the automatic fixes that would be made with -a")
@click.option("--fix", "-f", is_flag=True, help="prompt when there is a selectable fix available")
@click.option("--interactive", "-i", is_flag=True, help="ask what to do even if the only options are manual (implies -f)")
@click.argument("checks", nargs=-1)
@cli_context.pass_context
def check(ctx: Context, default: bool, automatic: bool, preview: bool, fix: bool, interactive: bool, checks: list[str]):
    if interactive and automatic:
        ctx.console.print("cannot use --interactive with --automatic")
        raise SystemExit(1)
    if preview and (automatic or fix or interactive):
        ctx.console.print("--preview cannot be used with other fix options")
        raise SystemExit(1)

    if ctx.config.rescan == RescanOption.AUTO and ctx.click_ctx:
        ctx.click_ctx.invoke(scan)

    if default:
        ctx.console.print("using default check config")
        ctx.config.checks = default_checks_config()
    if len(checks) > 0:
        # validate check names
        for check_name in checks:
            if check_name not in ALL_CHECK_NAMES:
                ctx.console.print(f"invalid check name: {check_name}")
                return
        # enable only specified checks
        for check_name in ALL_CHECK_NAMES:
            enabled = check_name in checks
            ctx.config.checks[check_name]["enabled"] = enabled

        while len(dependent_checks := required_disabled_checks(ctx.config.checks)) > 0:
            for dep, required_by in dependent_checks.items():
                ctx.console.print(
                    f"automatically enabling check [italic]{dep}[/italic] required by {' and '.join(f'[italic]{check}[/italic]' for check in required_by)}"
                )
                ctx.config.checks[dep]["enabled"] = True

    issues = run_enabled(ctx, automatic, preview, fix, interactive)
    if issues == 0:
        ctx.console.print("no issues")
