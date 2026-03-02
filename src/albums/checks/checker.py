import logging
from dataclasses import dataclass
from typing import Mapping, Sequence

from rich.markup import escape

from ..app import Context
from ..database import operations
from ..interactive.interact import interact
from ..library import scanner
from ..tagger.provider import AlbumTaggerProvider
from ..types import Album, CheckResult
from .all import ALL_CHECKS
from .base_check import Check
from .helpers import album_display_name

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckDisposition:
    album: Album
    passed: bool
    maybe_changed: bool
    user_quit: bool
    displayed: bool
    suppressed_failure_message: str | None


class Checker:
    ctx: Context
    _automatic: bool
    _preview: bool
    _fix: bool
    _interactive: bool

    def __init__(self, ctx: Context, automatic: bool, preview: bool, fix: bool, interactive: bool):
        if interactive and automatic:
            ctx.console.print("cannot use --interactive with --automatic")
            raise SystemExit(1)
        if preview and (automatic or fix or interactive):
            ctx.console.print("--preview cannot be used with other fix options")
            raise SystemExit(1)
        self.ctx = ctx
        self._automatic = automatic
        self._preview = preview
        self._fix = fix
        self._interactive = interactive

    def run_enabled(self) -> int:
        need_checks = self.get_required_disabled_checks()
        if need_checks:
            self.ctx.console.print("[bold red]Configuration error: some enabled checks depend on checks that are disabled:[/bold red]")
            for check, deps in need_checks.items():
                self.ctx.console.print(f"  [italic]{check}[/italic] required by {' and '.join(f'[italic]{dep}[/italic]' for dep in deps)}")
            raise SystemExit(1)
        if self._preview and (self._automatic or self._fix or self._interactive):
            raise ValueError("invalid preview setting")  # not allowed by cli
        preview_failed_checks: list[str] = []

        tagger = AlbumTaggerProvider(self.ctx.config.library)
        check_instances = [check(self.ctx, tagger) for check in ALL_CHECKS if self.ctx.config.checks[check.name]["enabled"]]

        issues_displayed = 0
        for album in self.ctx.select_albums(True):
            checks_passed: set[str] = set()
            preview_failed_checks = []
            for check in check_instances:
                if check.name not in album.ignore_checks:
                    missing_dependent_checks = check.must_pass_checks - checks_passed
                    if missing_dependent_checks:
                        for message in preview_failed_checks:
                            self.ctx.console.print(message, highlight=False)
                        preview_failed_checks = []
                        self.ctx.console.print(
                            f'[bold]dependency not met for check {check.name}[/bold] on "{album_display_name(self.ctx, album)}": {" and ".join(missing_dependent_checks)} must pass first',
                            highlight=False,
                        )
                        issues_displayed += 1
                    else:
                        disposition = self._run_check(check, album)
                        album = disposition.album
                        if disposition.passed:
                            checks_passed.add(check.name)
                        if disposition.suppressed_failure_message:
                            preview_failed_checks.append(disposition.suppressed_failure_message)
                        if disposition.displayed:
                            issues_displayed += 1
                else:
                    logger.debug(f"skipping ignored check {check.name} for album {album.path}")
        return issues_displayed

    def get_required_disabled_checks(self) -> Mapping[str, Sequence[str]]:
        check_classes = [check for check in ALL_CHECKS if self.ctx.config.checks[check.name]["enabled"]]
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

    def _run_check(self, check: Check, album: Album) -> CheckDisposition:
        maybe_changed = False
        maybe_fixable = True
        passed = False
        quit = False
        displayed = False
        suppressed_failure_message = None
        while maybe_fixable and not passed and not quit:
            check_result = check.check(album)
            if check_result:
                disposition = self._handle_check_result(check, check_result, album)
                if disposition.suppressed_failure_message:
                    suppressed_failure_message = disposition.suppressed_failure_message
                displayed |= disposition.displayed
                maybe_changed |= disposition.maybe_changed
                quit = disposition.user_quit

                if disposition.maybe_changed:
                    reread = True  # probably could be False -> faster
                    (_, any_changes) = scanner.scan(self.ctx, lambda: [(album.path, album.album_id)], reread)
                    maybe_fixable = any_changes
                    if self.ctx.db and album.album_id:
                        album = operations.load_album(self.ctx.db, album.album_id, True)
                else:
                    maybe_fixable = False
            else:
                passed = True
        return CheckDisposition(album, passed, maybe_changed, quit, displayed, suppressed_failure_message)

    def _handle_check_result(self, check: Check, check_result: CheckResult, album: Album) -> CheckDisposition:
        fixer = check_result.fixer
        displayed_any = False
        maybe_changed = False
        user_quit = False
        suppressed_failure_message = None
        if self._preview and fixer and fixer.option_automatic_index is not None:
            self.ctx.console.print(f'[bold]preview automatic fix {check.name}:[/bold] "{album_display_name(self.ctx, album)}"', highlight=False)
            self.ctx.console.print(f"    {escape(check_result.message)}", highlight=False)
            self.ctx.console.print(f"    {fixer.prompt}: {fixer.options[fixer.option_automatic_index]}", highlight=False)
            displayed_any = True
        elif self._automatic and fixer and fixer.option_automatic_index is not None:
            self.ctx.console.print(
                f'[bold]automatically fixing {check.name}:[/bold] "{album_display_name(self.ctx, album)}" - {escape(check_result.message)}',
                highlight=False,
            )
            self.ctx.console.print(f"    {fixer.prompt}: {fixer.options[fixer.option_automatic_index]}", highlight=False)
            maybe_changed = fixer.fix(fixer.options[fixer.option_automatic_index])
            displayed_any = True
        elif self._interactive or (fixer and self._fix):
            self.ctx.console.print()
            self.ctx.console.print(f'>> "{album_display_name(self.ctx, album)}"', highlight=False)
            (maybe_changed, user_quit) = interact(self.ctx, check.name, check_result, album)
            displayed_any = True
        else:
            message = f'[bold]{check.name}[/bold] {escape(check_result.message)} : "{album_display_name(self.ctx, album)}"'
            if self._preview:
                suppressed_failure_message = message
            else:
                self.ctx.console.print(message, highlight=False)
                displayed_any = True

        return CheckDisposition(album, False, maybe_changed, user_quit, displayed_any, suppressed_failure_message)
