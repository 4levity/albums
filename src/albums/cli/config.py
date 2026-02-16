import re
import sqlite3

import rich_click as click
from rich.markup import escape
from rich.table import Table

from albums.interactive.configurator import interactive_config, set_library

from ..app import Context
from ..database import configuration
from ..types import RescanOption
from . import cli_context


@click.command(help="reconfigure albums", epilog="use `albums config` with no options for interactive configuration")
@click.option("--show", "-s", is_flag=True, help="show the current configuration")
@click.argument("name", required=False)
@click.argument("value", required=False)
@cli_context.pass_context
def config(ctx: Context, show: bool, name: str, value: str):
    if not ctx.db:
        raise ValueError("config requires database connection")
    if name and not value:
        ctx.console.print("error: must specify both name and value, or neither")
        raise SystemExit(1)

    if show:
        table = Table("setting", "value")
        for k, v in ctx.config.to_values().items():
            table.add_row(k, escape(",".join(v) if isinstance(v, list) else str(v)))
        ctx.console.print(table)

    if name and value:
        _set(ctx, ctx.db, name, value)
        ctx.console.print(f"{name} = {value}")
    elif not show:
        interactive_config(ctx, ctx.db)


def _set(ctx: Context, db: sqlite3.Connection, setting_name: str, value: str):
    keys = setting_name.split(".")
    if len(keys) != 2:
        ctx.console.print(f"invalid setting {setting_name}")
        raise SystemExit(1)

    [section, name] = keys
    if section == "settings":
        if name == "library":
            set_library(ctx, db, value)
        elif name == "rescan":
            ctx.config.rescan = RescanOption(value)
            configuration.save(db, ctx.config)
        elif name == "tagger":
            ctx.config.tagger = value
            configuration.save(db, ctx.config)
        elif name == "open_folder_command":
            ctx.config.open_folder_command = value
            configuration.save(db, ctx.config)
        else:
            ctx.console.print(f"{setting_name} is not a valid setting")
            raise SystemExit(1)

    else:
        _set_check(ctx, section, name, value)
        configuration.save(db, ctx.config)


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
