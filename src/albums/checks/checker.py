from typing import Any
from rich.markup import escape

from .. import app
from ..checks.base_check import Check, CheckResult
from ..library import scanner
from ..types import Album
from .all import ALL_CHECKS
from .interact import interact


def run_enabled(ctx: app.Context, automatic: bool, preview: bool, fix: bool, interactive: bool):
    def handle_check_result(ctx: app.Context, check_result: CheckResult, album: Album):
        fixer = check_result.fixer
        rescan = False
        if preview:
            if fixer and fixer.option_automatic_index is not None:
                ctx.console.print(f'[bold]preview automatic fix:[/bold] {escape(check_result.message)} : "{escape(album.path)}"')
                ctx.console.print(f"    {fixer.prompt}: {fixer.options[fixer.option_automatic_index]}")
        elif automatic and fixer and fixer.option_automatic_index is not None:
            ctx.console.print(f'[bold]automatically fixing:[/bold] {escape(check_result.message)} : "{escape(album.path)}"')
            rescan = fixer.fix(fixer.options[fixer.option_automatic_index])
        elif interactive or (fixer and fix):
            ctx.console.print(f'>> "{album.path}"', markup=False)
            rescan = interact(ctx, check.name, check_result, album)
        else:
            ctx.console.print(f'{check_result.message} : "{album.path}"', markup=False)
        if rescan:
            scanner.scan(ctx, lambda: [(album.path, album.album_id)], True)

    check_instances = [check(ctx) for check in ALL_CHECKS if _enabled(ctx.config, check)]

    found_issues = 0
    for album in ctx.select_albums(True):
        for check in check_instances:
            if check.name not in album.ignore_checks:
                check_result = check.check(album)
                if check_result:
                    found_issues += 1
                    handle_check_result(ctx, check_result, album)
    return found_issues


def _enabled(config: dict[str, dict[str, Any]], check: type[Check]) -> bool:
    return config.get("checks", {}).get(check.name, {}).get("enabled", False)
