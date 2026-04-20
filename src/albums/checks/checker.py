import logging
from dataclasses import dataclass
from typing import Final, Mapping, Sequence

from rich.markup import escape
from sqlalchemy.orm import Session

from ..app import Context
from ..database import selector
from ..interactive.interact import interact, prompt_ignore_checks
from ..library import scanner
from ..tagger.provider import AlbumTaggerProvider
from ..types import Album, CheckResult, FixResult
from .all import ALL_CHECKS
from .base_check import Check
from .helpers import album_display_name

logger: Final = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckDisposition:
    # album: Album
    passed: bool
    maybe_changed: bool
    deleted: bool
    user_quit: bool
    displayed: bool
    suppressed_failure_message: str | None


class Checker:
    ctx: Context
    _automatic: bool
    _preview: bool
    _fix: bool
    _interactive: bool
    _show_ignore_option: bool

    def __init__(self, ctx: Context, automatic: bool, preview: bool, fix: bool, interactive: bool, show_ignore_option: bool):
        if preview and (automatic or fix or interactive):
            ctx.console.print("--preview cannot be used with other fix options")
            raise SystemExit(1)
        self.ctx = ctx
        self._automatic = automatic
        self._preview = preview
        self._fix = fix
        self._interactive = interactive
        self._show_ignore_option = show_ignore_option

    def run_enabled(self, session: Session) -> int:
        need_checks = self.get_required_disabled_checks()
        if need_checks:
            self.ctx.console.print("[bold red]Configuration error: some enabled checks depend on checks that are disabled:[/bold red]")
            for check, deps in need_checks.items():
                self.ctx.console.print(f"  [italic]{check}[/italic] required by {' and '.join(f'[italic]{dep}[/italic]' for dep in deps)}")
            raise SystemExit(1)
        if self._preview and (self._automatic or self._fix or self._interactive):
            raise ValueError("invalid preview setting")  # not allowed by cli
        preview_failed_checks: list[str] = []

        tagger = AlbumTaggerProvider(self.ctx.config.library, id3v1=self.ctx.config.id3v1)
        check_instances = [check(self.ctx, tagger=tagger, session=session) for check in ALL_CHECKS if self.ctx.config.checks[check.name]["enabled"]]

        issues_displayed = 0

        for album in self.ctx.select_album_entities(session):
            if not (self.ctx.config.library / album.path).is_dir():
                logger.info(f"album was deleted: {album.path}")
                scanner.scan(self.ctx, session, iter([album]))
                session.commit()
                continue
            logger.info(f"checking album: {album.path}")
            deleted = False
            check_all = True
            while check_all and not deleted:
                preview_failed_checks = []
                checks_passed: set[str] = set()
                check_all = False
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
                            if self._interactive and album.album_id is not None:
                                prompt_ignore_checks(session, album.album_id, check.name)

                            issues_displayed += 1

                        else:
                            disposition = self._run_check(session, check, album)
                            if disposition.displayed:
                                issues_displayed += 1
                            if disposition.deleted:
                                deleted = True
                                break  # don't run any more checks on this album
                            if disposition.maybe_changed:
                                logger.debug(f"commit changes after running {check.name}")
                                session.commit()
                                check_all = True  # re-run all checks
                                break  # from the beginning
                            elif disposition.passed:
                                checks_passed.add(check.name)
                            elif disposition.suppressed_failure_message:
                                preview_failed_checks.append(disposition.suppressed_failure_message)
                    else:
                        logger.debug(f"skipping ignored check {check.name} for album {album.path}")
        session.commit()
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

    def _run_check(self, session: Session, check: Check, album: Album) -> CheckDisposition:
        maybe_changed = False
        deleted = False
        maybe_fixable = True
        passed = False
        quit = False
        displayed = False
        suppressed_failure_message = None
        while maybe_fixable and not passed and not quit and not deleted:
            check_result = check.check(album)
            if check_result:
                disposition = self._handle_check_result(session, check, check_result, album)
                if disposition.suppressed_failure_message:
                    suppressed_failure_message = disposition.suppressed_failure_message
                displayed |= disposition.displayed
                maybe_changed |= disposition.maybe_changed
                quit = disposition.user_quit
                deleted = disposition.deleted

                if not deleted and disposition.maybe_changed:
                    session.flush()
                    path = album.path
                    (_, any_changes) = scanner.scan(self.ctx, session, selector.load_album_entities(session, path=[path]), reread=True)
                    maybe_fixable = any_changes
                elif deleted:
                    scanner.scan(self.ctx, session, iter([album]))  # delete immediately
                else:
                    maybe_fixable = False
            else:
                passed = True
        return CheckDisposition(passed, maybe_changed, deleted, quit, displayed, suppressed_failure_message)

    def _handle_check_result(self, session: Session, check: Check, check_result: CheckResult, album: Album) -> CheckDisposition:
        fixer = check_result.fixer
        displayed_any = False
        maybe_changed = False
        deleted = False
        user_quit = False
        suppressed_failure_message = None
        if self._preview and fixer and fixer.option_automatic_index is not None:
            self.ctx.console.print(
                f'[bold]preview automatic fix {check.name}:[/bold] [bold cyan]"{album_display_name(self.ctx, album)}"[/bold cyan]', highlight=False
            )
            self.ctx.console.print(f"    {escape(check_result.message)}", highlight=False)
            self.ctx.console.print(f"    {fixer.prompt}: {fixer.options[fixer.option_automatic_index]}", highlight=False)
            displayed_any = True
        elif self._automatic and fixer and fixer.option_automatic_index is not None:
            self.ctx.console.print(
                f'[bold]automatically fixing {check.name}:[/bold] [bold cyan]"{album_display_name(self.ctx, album)}"[/bold cyan] - [bold yellow]{escape(check_result.message)}[/bold yellow]',
                highlight=False,
            )
            self.ctx.console.print(f"    {fixer.prompt}: {fixer.options[fixer.option_automatic_index]}", highlight=False)
            fix_result = fixer.fix(fixer.options[fixer.option_automatic_index])
            maybe_changed = fix_result != FixResult.NO_CHANGE
            deleted = fix_result == FixResult.DELETED_ALBUM
            displayed_any = True
        elif self._interactive or (fixer and self._fix):
            self.ctx.console.print()
            self.ctx.console.print(f'>> [bold cyan]"{album_display_name(self.ctx, album)}"[/bold cyan]', highlight=False)
            (maybe_changed, deleted, user_quit) = interact(self.ctx, session, check.name, check_result, album, self._show_ignore_option)
            displayed_any = True
        else:
            message = f'[bold]{check.name}[/bold] [bold yellow]{escape(check_result.message)}[/bold yellow] : [bold cyan]"{album_display_name(self.ctx, album)}"[/bold cyan]'
            if self._preview:
                suppressed_failure_message = message
            else:
                self.ctx.console.print(message, highlight=False)
                displayed_any = True

        return CheckDisposition(False, maybe_changed, deleted, user_quit, displayed_any, suppressed_failure_message)
