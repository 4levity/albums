"""Click API with rich-rendered help output (local replacement for rich-click).

The CLI previously did ``import rich_click as click``. The rich-click package
imports ``click.utils.get_binary_stream``, ``click.utils.get_text_stream`` and
``click.utils.PacifyFlushWrapper``, all of which are deprecated in Click 8.5
(and scheduled for removal in Click 9.0), which broke the test suite's
``--max-warnings=0`` requirement.

This module replaces rich-click with a small, self-contained implementation:
it re-exports the regular ``click`` API, but the ``command``/``group``
decorators (and the ``RichCommand``/``RichGroup`` classes) render ``--help``
output as rich panels (usage line, options and commands panels, epilog) in the
same style rich-click used, and usage errors are rendered as a rich "Error"
panel. Import this module as ``click`` (e.g. ``import albums.cli.click_rich as
click``) to get the same behavior without the rich-click dependency.
"""

from __future__ import annotations

import inspect
import os
import sys
from typing import Any, cast

import click
from click import *  # noqa: F403  # pyright: ignore[reportWildcardImportFromLibrary, reportAssignmentType]  # re-export click's full public API
from click import command as _click_command
from click import group as _click_group
from click.exceptions import NoArgsIsHelpError  # not re-exported in click's top-level namespace
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# Default rich-click theme styles ("default" + "default-box" themes)
STYLE_USAGE: str = "yellow"
STYLE_USAGE_COMMAND: str = "bold"
STYLE_OPTION: str = "bold cyan"
STYLE_SWITCH: str = "bold green"
STYLE_METAVAR: str = "bold yellow"
STYLE_HELP: str = "dim"
STYLE_REQUIRED: str = "dim red"
STYLE_BORDER: str = "dim"
STYLE_ERROR_BORDER: str = "red"

# Console theme used to resolve the style names attached by the highlighters (rich-click parity)
_CONSOLE_THEME: Theme = Theme(
    {
        "option": STYLE_OPTION,
        "command": STYLE_OPTION,
        "argument": STYLE_OPTION,
        "switch": STYLE_SWITCH,
        "metavar": STYLE_METAVAR,
        "metavar_sep": "",
        "usage": STYLE_USAGE,
        "deprecated": "red",
    }
)


def _truthy(value: str) -> bool | None:
    """Interpret an environment variable value as a boolean (rich-click parity)."""
    if value.lower() in {"y", "yes", "t", "true", "1"}:
        return True
    if value.lower() in {"n", "no", "f", "false", "0"}:
        return False
    return None


def _force_terminal_default() -> bool | None:
    """Force color output when FORCE_COLOR / PY_COLORS / GITHUB_ACTIONS is set (rich-click parity)."""
    for env_var in ("FORCE_COLOR", "PY_COLORS", "GITHUB_ACTIONS"):
        if env_var in os.environ:
            return _truthy(os.environ[env_var])
    return None


def _make_console() -> Console:
    """Create the console used for help/error rendering: rich-click's default theme plus env-var color forcing."""
    return Console(theme=_CONSOLE_THEME, force_terminal=_force_terminal_default())


class _UsageHighlighter(RegexHighlighter):
    """Tag word tokens in the usage line so the console theme can style them (rich-click parity)."""

    highlights = [
        r"(?P<argument>\w+)",
    ]


class _HelpHighlighter(RegexHighlighter):
    """Tag option/switch/metavar/deprecated tokens in help text so the console theme can style them (rich-click parity)."""

    highlights = [
        r"(^|[^\w\-])(?P<switch>-([^\W0-9][\w\-]*\w|[^\W0-9]))",
        r"(^|[^\w\-])(?P<option>--([^\W0-9][\w\-]*\w|[^\W0-9]))",
        r"(?P<metavar><[^>]+>)",
        r"(?P<deprecated>\(DEPRECATED(?:\: .*?)?\))$",
    ]


_usage_highlighter = _UsageHighlighter()
_help_highlighter = _HelpHighlighter()


def _usage_text(ctx: click.Context) -> Columns:
    """Build the styled ``Usage: <prog> <args>`` line for *ctx*."""
    usage = ctx.get_usage().removeprefix("Usage: ")
    prog = ctx.command_path
    rest = usage.removeprefix(prog)
    rest = rest[1:] if rest.startswith(" ") else rest
    columns = [Text("Usage:", style=STYLE_USAGE), Text(prog, style=STYLE_USAGE_COMMAND)]
    if rest:
        columns.append(_usage_highlighter(Text(rest)))
    return Columns(columns)


def _styled_help_text(help: str | None) -> Text | None:
    """Build styled prose help text (first paragraph normal, remaining paragraphs dim); ``None`` when there is no help."""
    if not help:
        return None
    text = inspect.cleandoc(help)
    first_paragraph, _, rest = text.partition("\n\n")
    styled = _help_highlighter(Text(first_paragraph.replace("\n", " ").strip()))
    for paragraph in rest.split("\n\n") if rest else []:
        styled.append("\n")
        styled.append(_help_highlighter(Text(paragraph.replace("\n", " ").strip(), style=STYLE_HELP)))
    return styled


def _panel(title: str, table: Table) -> Panel:
    """Wrap *table* in a full-width, rounded, dim-bordered panel with a left-aligned title."""
    return Panel(table, title=title, title_align="left", box=box.ROUNDED, border_style=STYLE_BORDER, padding=(0, 1))


def _cell_text(cell: Text | Columns | None) -> str:
    if cell is None:
        return ""
    if isinstance(cell, Columns):
        return "".join(renderable.plain for renderable in cell.renderables if isinstance(renderable, Text))
    return cell.plain


def _table(columns: list[list[Text | Columns | None]], column_kwargs: list[dict[str, Any]] | None = None) -> Table | None:
    """Build a rich table from per-column cells, dropping columns whose cells are all empty (rich-click parity)."""
    kept: list[tuple[list[Text | Columns | None], int]] = []
    for index, column in enumerate(zip(*columns)):
        if any(_cell_text(cell) for cell in column):
            kept.append((list(column), index))
    if not kept:
        return None
    table = Table(box=None, show_header=False, expand=True, padding=(0, 1), pad_edge=False, highlight=True)
    for column, index in kept:
        table.add_column(**(column_kwargs[index] if column_kwargs else {}))
    for row in zip(*(cells for cells, _ in kept)):
        table.add_row(*row)
    return table


def _options_table(command: click.Command, ctx: click.Context) -> Table | None:
    """Build the "Options" table: long name, short name, metavar, help.

    Options appear in source (top-to-bottom) order, as click 8.5+ stores them. Arguments are not shown in the
    panel (rich-click's default).
    """
    options = [param for param in command.get_params(ctx) if isinstance(param, click.Option)]
    if not options:
        return None
    rows: list[list[Text | Columns | None]] = []
    for option in options:
        long_opts = [opt for opt in option.opts if opt.startswith("--")]
        short_opts = [opt for opt in option.opts if not opt.startswith("--")]
        long_name = long_opts[0] if long_opts else (option.opts[0] if option.opts else option.name)
        short_name = short_opts[0] if short_opts else ""
        metavar = option.make_metavar(ctx)
        if option.is_flag or option.count or metavar == "BOOLEAN":
            metavar = ""
        help_text = Text(option.help or "")
        if option.required and not option.is_flag:
            help_text.append("  [required]" if help_text.plain else "[required]", style=STYLE_REQUIRED)
        help_text = _help_highlighter(help_text)
        rows.append(
            [
                Text(long_name, style=STYLE_OPTION),
                Text(short_name, style=STYLE_SWITCH) if short_name else None,
                Text(metavar, style=STYLE_METAVAR) if metavar else None,
                Columns([help_text]) if help_text.plain else None,
            ]
        )
    return _table(rows)


def _commands_table(group: click.Group, ctx: click.Context) -> Table | None:
    """Build the "Commands" table: command name (in registration order) and short help."""
    rows: list[list[Text | Columns | None]] = []
    for name in group.list_commands(ctx):
        subcommand = group.get_command(ctx, name)
        if subcommand is None:
            continue
        help_text = (subcommand.short_help or "").strip() or (subcommand.help or "").strip().split("\n")[0]
        rows.append([Text(name, style=STYLE_OPTION), _help_highlighter(Text(help_text)) if help_text else None])
    if not rows:
        return None
    # The name column carries the command style so the padding spaces inherit it (rich-click parity)
    return _table(rows, column_kwargs=[{"style": STYLE_OPTION, "no_wrap": True}, {}])


class _RichHelp:
    """Mixin providing rich panel rendering of help and usage errors for click commands."""

    def get_help(self, ctx: click.Context) -> str:
        """Render the full help page (usage, prose, options/commands panels, epilog) as rich text."""
        console = _make_console()
        with console.capture() as capture:
            console.print(Padding(_usage_text(ctx), 1))
            if help_text := _styled_help_text(self.help):  # type: ignore[attr-defined]
                console.print(Padding(help_text, (0, 1, 1, 1)))
            if options := _options_table(self, ctx):  # type: ignore[arg-type]
                console.print(_panel("Options", options))
            if isinstance(self, click.Group) and (commands := _commands_table(self, ctx)):
                console.print(_panel("Commands", commands))
            if epilog := _styled_help_text(getattr(self, "epilog", None)):
                console.print(Padding(epilog, 1))
        # click's echo() appends the final newline when printing the help
        return capture.get().rstrip("\n")

    def main(
        self,
        args: Any = None,
        prog_name: Any = None,
        complete_var: Any = None,
        standalone_mode: bool = True,
        windows_expand_args: bool = True,
        **extra: Any,
    ) -> Any:
        """Run the command; in standalone mode render usage errors as a rich "Error" panel (rich-click parity)."""
        command = cast(click.Command, self)
        if not standalone_mode:
            return click.Command.main(
                command,
                args=args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=False,
                windows_expand_args=windows_expand_args,
                **extra,
            )
        try:
            return click.Command.main(
                command,
                args=args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=False,
                windows_expand_args=windows_expand_args,
                **extra,
            )
        except NoArgsIsHelpError as error:
            print(error.message)
            raise SystemExit(error.exit_code)
        except click.ClickException as error:
            self._print_rich_error(error)
            raise SystemExit(error.exit_code)
        except click.Abort:
            click.echo("Aborted!", file=sys.stderr)
            raise SystemExit(1)

    def _print_rich_error(self, error: click.ClickException) -> None:
        """Render a usage error the way rich-click did: usage line, optional "Try ... for help" suggestion, and an Error panel."""
        console = _make_console()
        with console.capture() as capture:
            if isinstance(error, click.UsageError) and error.ctx is not None:
                console.print(Padding(_usage_text(error.ctx), 1))
                self._print_help_suggestion(error.ctx, console)
            message = error.format_message() if isinstance(error, click.UsageError) else str(error)
            error_panel = Panel(_help_highlighter(Text(message)), title="Error", title_align="left", box=box.ROUNDED, border_style=STYLE_ERROR_BORDER)
            console.print(Padding(error_panel, (0, 0, 1, 0)))
        # print() (not click.echo), so color forcing survives piping (rich-click parity)
        print(capture.get().rstrip("\n"), file=sys.stderr)

    def _print_help_suggestion(self, ctx: click.Context, console: Console) -> None:
        """Print the "Try '<cmd> --help' for help" line when the command exposes a help option."""
        if ctx.command.get_help_option(ctx) is None or not ctx.help_option_names:
            return
        suggestion = Text()
        suggestion.append("Try ", style=STYLE_HELP)
        suggestion.append(f"'{ctx.command_path} {ctx.help_option_names[0]}'", style=STYLE_OPTION)
        suggestion.append(" for help", style=STYLE_HELP)
        console.print(Padding(suggestion, (0, 1, 0, 1)))


class RichCommand(_RichHelp, click.Command):
    """A click command whose help output is rendered as rich panels."""


class RichGroup(_RichHelp, click.Group):
    """A click group whose help output is rendered as rich panels, listing commands in registration order."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands.keys())


def _show_help_callback(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    """Print the help page on stdout and exit (rich-click's ``help_option`` callback)."""
    if value and not ctx.resilient_parsing:
        # print() directly: click.echo() would strip ANSI when piped (rich-click parity)
        if getattr(ctx, "help_to_stderr", False):
            print(ctx.get_help(), file=sys.stderr)
        else:
            print(ctx.get_help())
        ctx.exit()


def help_option(*param_decls: str, **attrs: Any) -> Any:
    """Equivalent to :func:`click.help_option`, printing via ``print()`` like rich-click's version did."""
    if not param_decls:
        param_decls = ("--help",)
    attrs.setdefault("is_flag", True)
    attrs.setdefault("expose_value", False)
    attrs.setdefault("is_eager", True)
    attrs.setdefault("help", "Show this message and exit.")
    attrs.setdefault("callback", _show_help_callback)
    return click.option(*param_decls, **attrs)


def command(name: str | None = None, cls: type[RichCommand] | None = None, **attrs: Any) -> Any:
    """Equivalent to :func:`click.command`, but creates a :class:`RichCommand` by default."""
    return _click_command(name=name, cls=cls or RichCommand, **attrs)


def group(name: str | None = None, cls: type[RichGroup] | None = None, **attrs: Any) -> Any:
    """Equivalent to :func:`click.group`, but creates a :class:`RichGroup` by default."""
    return _click_group(name=name, cls=cls or RichGroup, **attrs)
