"""Run the enabled checks (and fixes) against selected albums, in automatic, fix or interactive modes."""

import logging
import time
from dataclasses import dataclass
from typing import Final, Mapping, Sequence

from rich.markup import escape
from sqlalchemy.orm import Session

from albums.app import Context
from albums.entities import Album
from albums.interactive import interact, prompt_ignore_checks
from albums.library import run_scan
from albums.selector import Match, load_album_entities, preload_albums
from albums.tagger import AlbumTaggerProvider

from .all import ALL_CHECKS, implicitly_ignored_checks
from .base_check import Check
from .check_timing import CheckTiming, check_timing_table, estimate_seconds, format_album_count, format_seconds
from .check_types import CheckResult, FixResult
from .helpers import album_display_name

logger: Final = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckDisposition:
    """Outcome of running one check on one album: pass/fail, whether files changed or the album was deleted, user interaction results."""

    passed: bool
    maybe_changed: bool
    deleted: bool
    user_quit: bool
    displayed: bool


class Checker:
    """Orchestrate the enabled checks for a context, fixing issues and re-running checks until the album is stable.

    With ``timing=True``, ``run_enabled`` measures each enabled check's init time and every
    ``check(album)`` call (pass or fail) and prints a timing report at the end of the run.
    """

    ctx: Context
    _automatic: bool
    _fix: bool
    _interactive: bool
    _show_ignore_option: bool
    _timing: bool

    def __init__(self, ctx: Context, automatic: bool, fix: bool, interactive: bool, show_ignore_option: bool, timing: bool = False):
        self.ctx = ctx
        self._automatic = automatic
        self._fix = fix
        self._interactive = interactive
        self._show_ignore_option = show_ignore_option
        self._timing = timing
        # per-check timing stats, populated by run_enabled when timing is enabled
        self.timings: dict[str, CheckTiming] = {}

    def run_enabled(self, session: Session) -> int:
        """Run all enabled checks on each selected album, honoring dependencies, ignoring and fixes; returns the issue count displayed.

        ``_run_check`` flushes (not commits) after each applied fix so the post-fix re-scan
        sees the changes; the ``Checker`` commits after the re-scan and at the end of the run
        (a deleted album's rows are committed at the end of the run and self-heal on the next
        run if the run is interrupted). See the ``Fixer`` docstring for the fixer contract.
        """
        need_checks = self.get_required_disabled_checks()
        if need_checks:
            self.ctx.console.print("[bold red]Configuration error: some enabled checks depend on checks that are disabled:[/bold red]")
            for check, deps in need_checks.items():
                self.ctx.console.print(f"  [italic]{check}[/italic] required by {' and '.join(f'[italic]{dep}[/italic]' for dep in deps)}")
            raise SystemExit(1)
        tagger = AlbumTaggerProvider(self.ctx.config.library, id3v1=self.ctx.config.id3v1)
        enabled_checks: list[type[Check]] = [check for check in ALL_CHECKS if self.ctx.config.checks[check.name]["enabled"]]
        if self._timing:
            self.timings = {check.name: CheckTiming() for check in enabled_checks}
        check_instances: list[Check] = []
        for check in enabled_checks:
            if self._timing:
                start = time.perf_counter()
                instance = check(self.ctx, tagger=tagger, session=session)
                self.timings[check.name].init_seconds = time.perf_counter() - start
            else:
                instance = check(self.ctx, tagger=tagger, session=session)
            check_instances.append(instance)

        issues_displayed = 0
        albums_checked = 0

        albums = list(self.ctx.select_album_entities(session))
        # checks read track pictures and legacy fields per track; preload so the run
        # issues a handful of batched queries instead of one per track per album. Commits
        # expire the loaded relationships, so after one the remainder is preloaded again.
        preload_albums(session, (album.album_id for album in albums))

        for ix, album in enumerate(albums):
            if not (self.ctx.config.library / album.path).is_dir():
                logger.info(f"album was deleted: {album.path}")
                run_scan(self.ctx, session, iter([album]))
                session.commit()
                preload_albums(session, (other.album_id for other in albums[ix + 1 :]))
                continue
            albums_checked += 1
            logger.info(f"checking album: {album.path}")
            deleted = False
            check_all = True
            while check_all and not deleted:
                checks_passed: set[str] = set()
                check_all = False
                for check in check_instances:
                    ignored = set(album.ignore_checks)
                    if check.name in ignored:
                        logger.debug(f"skipping ignored check {check.name} for album {album.path}")
                    elif check.name in implicitly_ignored_checks(ignored):
                        logger.debug(f"skipping implicitly ignored check {check.name} for album {album.path}, a check it depends on is ignored")
                    else:
                        missing_dependent_checks = check.must_pass_checks - checks_passed
                        if missing_dependent_checks:
                            self.ctx.console.print(
                                f'[bold]dependency not met for check {check.name}[/bold] on "{album_display_name(self.ctx, album)}": {" and ".join(missing_dependent_checks)} must pass first',
                                highlight=False,
                            )
                            if self._interactive and album.album_id is not None:
                                prompt_ignore_checks(self.ctx, session, album.album_id, check.name)

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
                                preload_albums(session, (other.album_id for other in albums[ix:]))
                                check_all = True  # re-run all checks
                                break
                            elif disposition.passed:
                                checks_passed.add(check.name)
        session.commit()
        if self._timing:
            self._print_timings(albums_checked)
        return issues_displayed

    def _print_timings(self, albums_checked: int):
        """Print the per-check timing report: measured init and pass/fail times, plus a linear estimate for other library sizes."""
        console = self.ctx.console
        console.print(f"[bold]check timings[/bold] (wall clock, {albums_checked} albums)")
        console.print(check_timing_table(self.timings, (check.name for check in ALL_CHECKS)))
        if albums_checked:
            estimates = ", ".join(
                f"{format_album_count(count)}: {format_seconds(estimate_seconds(self.timings, albums_checked, count))}"
                for count in (10_000, 100_000, 1_000_000)
            )
            console.print(
                f"[dim]estimate, same per-album cost and issue rate: {estimates} (init grows with library size, e.g. duplicate-album)[/dim]"
            )

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
        while maybe_fixable and not passed and not quit and not deleted:
            if self._timing:
                start = time.perf_counter()
                check_result = check.check(album)
                self.timings[check.name].record(check_result is not None, time.perf_counter() - start)
            else:
                check_result = check.check(album)
            if check_result:
                disposition = self._handle_check_result(session, check, check_result, album)
                displayed |= disposition.displayed
                maybe_changed |= disposition.maybe_changed
                quit = disposition.user_quit
                deleted = disposition.deleted

                if not deleted and disposition.maybe_changed:
                    session.flush()
                    path = album.path
                    (_, any_changes) = run_scan(self.ctx, session, load_album_entities(session, {"path": [Match(path)]}), reread=True)
                    maybe_fixable = any_changes
                elif deleted:
                    run_scan(self.ctx, session, iter([album]))  # delete immediately
                else:
                    maybe_fixable = False
            else:
                passed = True
        return CheckDisposition(passed, maybe_changed, deleted, quit, displayed)

    def _handle_check_result(self, session: Session, check: Check, check_result: CheckResult, album: Album) -> CheckDisposition:
        fixer = check_result.fixer
        displayed_any = False
        maybe_changed = False
        deleted = False
        user_quit = False
        if self._automatic and fixer and fixer.option_automatic_index is not None:
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
            self.ctx.console.print(message, highlight=False)
            displayed_any = True

        return CheckDisposition(False, maybe_changed, deleted, user_quit, displayed_any)
