from typing import Any
from rich.markup import escape

import albums.database.operations
from .. import app
from ..checks.base_check import Check, CheckResult
from ..library import scanner
from ..types import Album
from .all import ALL_CHECKS
from .interact import interact


def run_enabled(ctx: app.Context, automatic: bool, preview: bool, fix: bool, interactive: bool):
    def handle_check_result(ctx: app.Context, check: Check, check_result: CheckResult, album: Album):
        fixer = check_result.fixer
        displayed_any = False
        maybe_changed = False
        user_quit = False
        if preview:
            if fixer and fixer.option_automatic_index is not None:
                ctx.console.print(f'[bold]preview automatic fix:[/bold] "{escape(album.path)}" - {escape(check_result.message)}')
                ctx.console.print(f"    {fixer.prompt}: {fixer.options[fixer.option_automatic_index]}")
                displayed_any = True
        elif automatic and fixer and fixer.option_automatic_index is not None:
            ctx.console.print(f'[bold]automatically fixing:[/bold] "{escape(album.path)}" - {escape(check_result.message)}')
            ctx.console.print(f"    {fixer.prompt}: {fixer.options[fixer.option_automatic_index]}")
            maybe_changed = fixer.fix(fixer.options[fixer.option_automatic_index])
            displayed_any = True
        elif interactive or (fixer and fix):
            ctx.console.print(f'>> "{album.path}"', markup=False)
            (maybe_changed, user_quit) = interact(ctx, check.name, check_result, album)
            displayed_any = True
        else:
            ctx.console.print(f'{check_result.message} : "{album.path}"', markup=False)
            displayed_any = True

        return (maybe_changed, user_quit, displayed_any)

    check_instances = [check(ctx) for check in ALL_CHECKS if _enabled(ctx.config, check)]

    showed_issues = 0
    for album in ctx.select_albums(True):
        for check in check_instances:
            if check.name not in album.ignore_checks:
                maybe_fixable = True
                fixed = False
                quit = False
                while maybe_fixable and not fixed and not quit:
                    check_result = check.check(album)
                    if check_result:
                        (took_action, quit, displayed) = handle_check_result(ctx, check, check_result, album)
                        showed_issues += 1 if displayed else 0
                        if took_action:
                            reread = True  # probably could be False -> faster
                            (_, tracks_changed) = scanner.scan(ctx, lambda: [(album.path, album.album_id)], reread)
                            maybe_fixable = tracks_changed
                            if maybe_fixable and ctx.db and album.album_id:
                                # reload album so we can check it again
                                album = albums.database.operations.load_album(ctx.db, album.album_id, True)
                        else:
                            maybe_fixable = False
                    else:
                        fixed = True

    return showed_issues


def _enabled(config: dict[str, dict[str, Any]], check: type[Check]) -> bool:
    return config.get("checks", {}).get(check.name, {}).get("enabled", check.default_config["enabled"])
