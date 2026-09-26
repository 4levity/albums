from sqlalchemy.orm import Session

import albums.cli.click_rich as click
from albums.app import Context, require_library, require_real_context
from albums.checks.all import ALL_CHECK_NAMES
from albums.checks.checker import Checker
from albums.config import RescanOption
from albums.library import run_scan

from .cli_context import pass_context


@click.command(
    help="report and sometimes fix issues in selected albums",
    epilog=f"If CHECKS are provided, only those checks and their dependencies will be enabled. Valid CHECKS are: {', '.join(sorted(ALL_CHECK_NAMES))}",
    add_help_option=False,
)
@click.option("--automatic", "-a", is_flag=True, help="if there is an automatic fix, do it WITHOUT ASKING")  # pyright: ignore[reportUnknownMemberType]
@click.option("--fix", "-f", is_flag=True, help="prompt when there is a selectable fix available")  # pyright: ignore[reportUnknownMemberType]
@click.option("--interactive", "-i", is_flag=True, help="ask what to do even if the only options are manual (implies -f)")  # pyright: ignore[reportUnknownMemberType]
@click.option("--timing", is_flag=True, help="report per-check wall-clock timing (init, pass and fail) after the run")  # pyright: ignore[reportUnknownMemberType]
@click.argument("checks", nargs=-1)  # pyright: ignore[reportUnknownMemberType]
@click.help_option("--help", "-h", help="show this message and exit")  # pyright: ignore[reportUnknownMemberType]
@pass_context
def check(ctx: Context, automatic: bool, fix: bool, interactive: bool, timing: bool, checks: list[str]):
    require_real_context(ctx)
    require_library(ctx)
    if ctx.config.rescan == RescanOption.AUTO and ctx.is_persistent:
        ctx.console.print("Scanning library before check (see config settings.rescan to disable this)")
        run_scan(ctx)

    # when specific checks are requested, only those (plus their dependencies) are enabled in a
    # working copy of the configuration, leaving the stored configuration in the context unchanged
    working_config = ctx.config
    if len(checks) > 0:
        # validate check names
        for check_name in checks:
            if check_name not in ALL_CHECK_NAMES:
                ctx.console.print(f"invalid check name: {check_name}")
                return
        working_config = ctx.config.copy()
        for check_name in ALL_CHECK_NAMES:
            working_config.checks[check_name]["enabled"] = check_name in checks

    checker = Checker(ctx, working_config, automatic, fix, interactive, show_ignore_option=ctx.is_persistent, timing=timing)
    if len(checks) > 0:
        while len(dependent_checks := checker.get_required_disabled_checks()) > 0:
            for dep, required_by in dependent_checks.items():
                ctx.console.print(
                    f"automatically enabling check [italic]{dep}[/italic] required by {' and '.join(f'[italic]{check}[/italic]' for check in required_by)}"
                )
                working_config.checks[dep]["enabled"] = True
    with Session(ctx.db) as session:
        issues_displayed = checker.run_enabled(session, ctx.album_selector())

    if issues_displayed == 0:
        ctx.console.print("no issues")
