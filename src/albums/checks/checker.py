from typing import Any

from rich.markup import escape

from .. import app
from ..checks.base_check import Check, CheckResult
from ..database import operations
from ..library import scanner
from ..types import Album
from .all import ALL_CHECKS
from .interact import interact


def run_enabled(ctx: app.Context, automatic: bool, preview: bool, fix: bool, interactive: bool):
    need_checks = required_disabled_checks(ctx.config)
    if need_checks:
        ctx.console.print("[bold red]Configuration error: some enabled checks depend on checks that are disabled:[/bold red]")
        for check, deps in need_checks.items():
            ctx.console.print(f"  [italic]{check}[/italic] required by {' and '.join(f'[italic]{dep}[/italic]' for dep in deps)}")
        raise SystemExit(1)
    if preview and (automatic or fix or interactive):
        raise ValueError("invalid preview setting")  # not allowed by cli
    preview_failed_checks: list[str] = []

    def handle_check_result(ctx: app.Context, check: Check, check_result: CheckResult, album: Album):
        fixer = check_result.fixer
        displayed_any = False
        maybe_changed = False
        user_quit = False
        if preview and fixer and fixer.option_automatic_index is not None:
            ctx.console.print(f'[bold]preview automatic fix {check.name}:[/bold] "{escape(album.path)}"', highlight=False)
            ctx.console.print(f"    {escape(check_result.message)}", highlight=False)
            ctx.console.print(f"    {fixer.prompt}: {fixer.options[fixer.option_automatic_index]}", highlight=False)
            displayed_any = True
        elif automatic and fixer and fixer.option_automatic_index is not None:
            ctx.console.print(
                f'[bold]automatically fixing {check.name}:[/bold] "{escape(album.path)}" - {escape(check_result.message)}', highlight=False
            )
            ctx.console.print(f"    {fixer.prompt}: {fixer.options[fixer.option_automatic_index]}", highlight=False)
            maybe_changed = fixer.fix(fixer.options[fixer.option_automatic_index])
            displayed_any = True
        elif interactive or (fixer and fix):
            ctx.console.print()
            ctx.console.print(f'>> "{album.path}"', highlight=False, markup=False)
            (maybe_changed, user_quit) = interact(ctx, check.name, check_result, album)
            displayed_any = True
        else:
            message = f'[bold]{check.name}[/bold] {escape(check_result.message)} : "{escape(album.path)}"'
            if preview:
                preview_failed_checks.append(message)
            else:
                ctx.console.print(message, highlight=False)
                displayed_any = True

        return (maybe_changed, user_quit, displayed_any)

    check_instances = [check(ctx) for check in ALL_CHECKS if _enabled_check(ctx.config, check)]

    showed_issues = 0
    for album in ctx.select_albums(True):
        checks_passed: set[str] = set()
        preview_failed_checks = []
        for check in check_instances:
            if check.name not in album.ignore_checks:
                missing_dependent_checks = check.must_pass_checks - checks_passed
                if missing_dependent_checks:
                    for message in preview_failed_checks:
                        ctx.console.print(message, highlight=False)
                    ctx.console.print(
                        f'[bold]dependency not met for check {check.name}[/bold] on "{escape(album.path)}": {" and ".join(missing_dependent_checks)} must pass first',
                        highlight=False,
                    )
                    showed_issues += 1
                    continue

                maybe_fixable = True
                passed = False
                quit = False
                while maybe_fixable and not passed and not quit:
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
                                album = operations.load_album(ctx.db, album.album_id, True)
                        else:
                            maybe_fixable = False
                    else:
                        passed = True
                if passed:
                    checks_passed.add(check.name)

    return showed_issues


def required_disabled_checks(config: dict[str, dict[str, Any]]):
    check_classes = [check for check in ALL_CHECKS if _enabled_check(config, check)]
    enabled = set(check.name for check in check_classes)
    required_disabled: dict[str, list[str]] = {}
    for check in check_classes:
        for dep in check.must_pass_checks:
            if dep not in enabled:
                if dep in required_disabled:
                    required_disabled[dep].append(check.name)
                else:
                    required_disabled[dep] = [check.name]
    return required_disabled


def _enabled_check(config: dict[str, dict[str, Any]], check: type[Check]) -> bool:
    return config.get("checks", {}).get(check.name, {}).get("enabled", check.default_config["enabled"])
