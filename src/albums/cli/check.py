from sqlalchemy.orm import Session

import albums.cli.click_rich as click
from albums.app import Context
from albums.checks.all import ALL_CHECK_NAMES
from albums.checks.checker import Checker
from albums.config import RescanOption, default_checks_config
from albums.library import run_scan

from .cli_context import pass_context, require_library, require_real_context


@click.command(
    help="report and sometimes fix issues in selected albums",
    epilog=f"If CHECKS are provided, only those checks and their dependencies will be enabled. Valid CHECKS are: {', '.join(sorted(ALL_CHECK_NAMES))}",
    add_help_option=False,
)
@click.option("--default", is_flag=True, help="use default settings for all checks, including whether they are enabled")  # pyright: ignore[reportUnknownMemberType]
@click.option("--automatic", "-a", is_flag=True, help="if there is an automatic fix, do it WITHOUT ASKING")  # pyright: ignore[reportUnknownMemberType]
@click.option("--preview", "-p", is_flag=True, help="preview the automatic fixes that would be made with -a")  # pyright: ignore[reportUnknownMemberType]
@click.option("--fix", "-f", is_flag=True, help="prompt when there is a selectable fix available")  # pyright: ignore[reportUnknownMemberType]
@click.option("--interactive", "-i", is_flag=True, help="ask what to do even if the only options are manual (implies -f)")  # pyright: ignore[reportUnknownMemberType]
@click.argument("checks", nargs=-1)  # pyright: ignore[reportUnknownMemberType]
@click.help_option("--help", "-h", help="show this message and exit")  # pyright: ignore[reportUnknownMemberType]
@pass_context
def check(ctx: Context, default: bool, automatic: bool, preview: bool, fix: bool, interactive: bool, checks: list[str]):
    require_real_context(ctx)
    require_library(ctx)
    if ctx.config.rescan == RescanOption.AUTO and ctx.is_persistent:
        ctx.console.print("Scanning library before check (see config settings.rescan to disable this)")
        run_scan(ctx)

    if default:
        ctx.console.print("using default check config")
        ctx.config.checks = default_checks_config()

    checker = Checker(ctx, automatic, preview, fix, interactive, show_ignore_option=ctx.is_persistent)
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

        while len(dependent_checks := checker.get_required_disabled_checks()) > 0:
            for dep, required_by in dependent_checks.items():
                ctx.console.print(
                    f"automatically enabling check [italic]{dep}[/italic] required by {' and '.join(f'[italic]{check}[/italic]' for check in required_by)}"
                )
                ctx.config.checks[dep]["enabled"] = True
    with Session(ctx.db) as session:
        issues_displayed = checker.run_enabled(session)

    if issues_displayed == 0:
        ctx.console.print("no issues")
