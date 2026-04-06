import json
import logging
import os
import re
from itertools import chain
from pathlib import Path
from string import Template
from typing import Mapping

import rich_click as click
from prompt_toolkit.shortcuts import confirm
from rich.markup import escape
from rich.table import Table

from ..app import Context
from ..config import Configuration, ID3v1Policy, PathCompatibilityOption, RescanOption, SettingValueType
from ..database import db_config
from ..interactive.configurator import interactive_config
from ..interactive.setup_settings import set_library
from .cli_context import pass_context, require_configured, require_persistent_context

logger = logging.getLogger(__name__)


@click.command(
    help="view and change the configuration in the database",
    epilog="use `albums config` with no options for interactive configuration",
    add_help_option=False,
)
@click.option("--show", "-s", is_flag=True, help="show the current configuration")
@click.option("--import", "-i", "import_file", metavar="FILE", help="import configuration from JSON file")
@click.option("--export", "-e", "export_file", metavar="FILE", help="export configuration to JSON file")
@click.option("--reset", is_flag=True, help="reset the configuration to defaults")
@click.argument("kv", metavar="[NAME=VALUE] [NAME]", required=False)
@click.help_option("--help", "-h", help="show this message and exit")
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
                k, "[bold]*[/bold]" if defaults[k] != v else "", _render_setting(k, v), _render_setting(k, defaults[k]) if defaults[k] != v else ""
            )
        ctx.console.print(table)

    if kv:
        if str.count(kv, "=") < 1:
            if kv in config_values:
                ctx.console.print(f"{kv} = {_render_setting(kv, config_values[kv])}", soft_wrap=True)
            else:
                ctx.console.print(f"invalid setting {kv}")
                raise SystemExit(1)
        else:
            [name, value] = kv.split("=", 1)
            if _set(ctx, name, value):
                ctx.console.print(f"{name} = {_render_setting(name, ctx.config.to_values()[name])}", soft_wrap=True)
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


def _render_setting(key: str, value: SettingValueType):
    if key == "settings.id3v1" and isinstance(value, int):
        return ID3v1Policy(int(value)).name
    if key == "settings.sync_destinations" and isinstance(value, list):
        return escape(",".join(str(v["collection"]) for v in value if isinstance(v, dict)))
    if isinstance(value, list):
        return escape(",".join(str(v) for v in value))
    return escape(str(value))


def _set(ctx: Context, setting_name: str, value: str) -> bool:
    keys = setting_name.split(".")
    if len(keys) != 2:
        ctx.console.print(f"invalid setting {setting_name}")
        return False

    [section, name] = keys
    if section == "settings":
        if name == "default_import_path":
            ctx.config.default_import_path = Template(value)
            db_config.save(ctx.db, ctx.config)
        elif name == "default_import_path_various":
            ctx.config.default_import_path_various = Template(value)
            db_config.save(ctx.db, ctx.config)
        elif name == "id3v1":
            ctx.config.id3v1 = ID3v1Policy[str.upper(value)]
            db_config.save(ctx.db, ctx.config)
        elif name == "import_scan_max_paths":
            ctx.config.import_scan_max_paths = int(value)
            db_config.save(ctx.db, ctx.config)
        elif name == "library":
            set_library(ctx, value)
        elif name == "more_import_paths":
            ctx.config.more_import_paths = [Template(v) for v in value.split(",")]
            db_config.save(ctx.db, ctx.config)
        elif name == "open_folder_command":
            ctx.config.open_folder_command = value
            db_config.save(ctx.db, ctx.config)
        elif name == "path_compatibility":
            ctx.config.path_compatibility = PathCompatibilityOption(value)
            db_config.save(ctx.db, ctx.config)
        elif name == "path_replace_invalid":
            ctx.config.path_replace_invalid = value
            db_config.save(ctx.db, ctx.config)
        elif name == "path_replace_slash":
            ctx.config.path_replace_slash = value
            db_config.save(ctx.db, ctx.config)
        elif name == "rescan":
            ctx.config.rescan = RescanOption(value)
            db_config.save(ctx.db, ctx.config)
        elif name == "tagger":
            ctx.config.tagger = value
            db_config.save(ctx.db, ctx.config)
        elif name == "sync_destinations":
            ctx.console.print("Use interactive config or import to create or update sync destinations")
            return False
        else:
            ctx.console.print(f"{setting_name} is not a valid setting")
            return False

    else:
        _set_check(ctx, section, name, value)
        db_config.save(ctx.db, ctx.config)
    return True


def _set_check(ctx: Context, check_name: str, name: str, value: str):
    if check_name not in ctx.config.checks:
        ctx.console.print(f"{check_name} is not a valid check name")
        raise SystemExit(1)

    config = ctx.config.checks[check_name]
    if name not in config:
        ctx.console.print(f"{name} is not a valid option for check {check_name}")
        raise SystemExit(1)
    if isinstance(config[name], list):
        config[name] = value.split(",")
    elif isinstance(config[name], str):
        config[name] = value
    elif isinstance(config[name], bool):
        if str.lower(value) not in {"true", "false", "t", "f"}:
            ctx.console.print(f"{check_name}.{name} must be true or false")
            raise SystemExit(1)
        config[name] = str.lower(value) in {"true", "t"}
    elif isinstance(config[name], float):
        if not re.fullmatch("\\d+(\\.\\d+)?", value):
            ctx.console.print(f"{check_name}.{name} must be a non-negative floating point number")
            raise SystemExit(1)
        config[name] = float(value)
    elif isinstance(config[name], int):
        if not re.fullmatch("\\d+", value):
            ctx.console.print(f"{check_name}.{name} must be a non-negative integer")
            raise SystemExit(1)
        config[name] = int(value)
    else:
        raise ValueError(f"{check_name}.{name} has unexpected type {type(config[name])}")
