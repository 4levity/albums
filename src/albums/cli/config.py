import json
import logging
import os
from itertools import chain
from pathlib import Path
from typing import Final, Mapping

import rich_click as click
from prompt_toolkit.shortcuts import confirm
from rich.markup import escape
from rich.table import Table

from ..app import Context
from ..config import Configuration, SettingValueType
from ..database import db_config
from ..interactive.configurator import interactive_config
from .cli_context import pass_context, require_configured, require_persistent_context
from .config_settings import render_setting, set_setting

logger: Final = logging.getLogger(__name__)


@click.command(
    help="view and change the configuration in the database",
    epilog="use `albums config` with no options for interactive configuration",
    add_help_option=False,
)
@click.option("--show", "-s", is_flag=True, help="show the current configuration")  # pyright: ignore[reportUnknownMemberType]
@click.option("--import", "-i", "import_file", metavar="FILE", help="import configuration from JSON file")  # pyright: ignore[reportUnknownMemberType]
@click.option("--export", "-e", "export_file", metavar="FILE", help="export configuration to JSON file")  # pyright: ignore[reportUnknownMemberType]
@click.option("--reset", is_flag=True, help="reset the configuration to defaults")  # pyright: ignore[reportUnknownMemberType]
@click.argument("kv", metavar="[NAME=VALUE] [NAME]", required=False)  # pyright: ignore[reportUnknownMemberType]
@click.help_option("--help", "-h", help="show this message and exit")  # pyright: ignore[reportUnknownMemberType]
@pass_context
def config(ctx: Context, show: bool, import_file: str, export_file: str, reset: bool, kv: str):
    require_configured(ctx)
    require_persistent_context(ctx)

    if sum(1 if opt else 0 for opt in [show, import_file, export_file, reset, kv]) > 1:
        ctx.console.print("The options --show, --import, --export, --reset and NAME are exclusive - you can only use one at a time")
        raise SystemExit(1)

    config_values = ctx.config.to_values()
    if show:
        table = Table("setting", "set", "value", "default (if different)", row_styles=["bold", ""])
        defaults = Configuration().to_values()
        for k, v in sorted(config_values.items(), key=lambda i: i[0]):
            table.add_row(
                k, "[bold]*[/bold]" if defaults[k] != v else "", render_setting(k, v), render_setting(k, defaults[k]) if defaults[k] != v else ""
            )
        ctx.console.print(table)

    if kv:
        if str.count(kv, "=") < 1:
            if kv in config_values:
                ctx.console.print(f"{kv} = {render_setting(kv, config_values[kv])}", soft_wrap=True)
            else:
                ctx.console.print(f"invalid setting {kv}")
                raise SystemExit(1)
        else:
            [name, value] = kv.split("=", 1)
            if set_setting(ctx, name, value):
                ctx.console.print(f"{name} = {render_setting(name, ctx.config.to_values()[name])}", soft_wrap=True)
            else:
                raise SystemExit(1)
    elif import_file:
        _import(ctx, import_file)
    elif export_file:
        _export(ctx, export_file)
    elif reset:
        _reset(ctx)
    elif not show:
        interactive_config(ctx)


def _import(ctx: Context, import_file: str):
    try:
        contents = Path(import_file).read_text(encoding="utf-8")
    except Exception as ex:
        logger.error(f'error reading file "{import_file}": {repr(ex)}')
        raise SystemExit(1)
    try:
        config_map: Mapping[str, SettingValueType] = json.loads(contents)
        config_items = config_map.items()
    except Exception as ex:
        logger.error(f'error parsing file "{import_file}": {repr(ex)}')
        raise SystemExit(1)

    (new_config, ignored) = Configuration.from_values(chain(ctx.config.to_values().items(), ((k, v) for k, v in config_items)))
    if (
        ignored
        and ctx.console.is_interactive
        and not confirm("Some values from a different version of albums were ignored. Are you sure you want to import this configuration?")
    ):
        ctx.console.print("Aborted")
        raise SystemExit(1)

    if new_config.library != ctx.config.library:
        ctx.console.print(
            f'Importing this configuration will change the library directory from "{str(ctx.config.library)}" to "{str(new_config.library)}" without changing the database contents.'
        )
        if ctx.console.is_interactive and confirm("Do you want to keep your existing library directory setting?"):
            new_config.library = ctx.config.library

        if not new_config.library.is_dir():
            ctx.console.print(f"Aborted configuration import: cannot access library directory at {str(new_config.library)}")
            raise SystemExit(1)

    db_config.save(ctx.db, new_config)
    ctx.console.print(f"imported configuration from {escape(import_file)}")


def _export(ctx: Context, export_file: str):
    config_json = json.dumps(ctx.config.to_values(), indent=4) + os.linesep
    path = Path(export_file)
    if path.exists():
        ctx.console.print(f"file already exists, not overwriting: {escape(export_file)}")
        raise SystemExit(1)
    try:
        path.write_text(config_json, encoding="utf-8")
        ctx.console.print(f"wrote {escape(export_file)}")
    except Exception as ex:
        logger.error(f'error writing to file "{export_file}": {repr(ex)}')
        raise SystemExit(1)


def _reset(ctx: Context):
    if ctx.console.is_interactive and not confirm("Are you sure you want to reset the configuration?"):
        raise SystemExit(1)
    new_config = Configuration()
    new_config.library = ctx.config.library
    db_config.save(ctx.db, new_config)
    ctx.console.print(f'Configuration reset to default except for library directory "{escape(str(ctx.config.library))}"')
