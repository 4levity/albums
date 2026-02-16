import re
import sqlite3
from pathlib import Path
from typing import Literal

import rich_click as click
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.shortcuts import checkboxlist_dialog, choice
from rich.markup import escape
from rich.prompt import FloatPrompt, IntPrompt
from rich.table import Table

from albums.config import RescanOption

from .. import app
from ..database import configuration
from . import cli_context


@click.command(help="reconfigure albums", epilog="use `albums config` with no options for interactive configuration")
@click.option("--show", "-s", is_flag=True, help="show the current configuration")
@click.argument("name", required=False)
@click.argument("value", required=False)
@cli_context.pass_context
def config(ctx: app.Context, show: bool, name: str, value: str):
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
        _interactive_config(ctx, ctx.db)


def _set(ctx: app.Context, db: sqlite3.Connection, setting_name: str, value: str):
    keys = setting_name.split(".")
    if len(keys) != 2:
        ctx.console.print(f"invalid setting {setting_name}")
        raise SystemExit(1)

    [section, name] = keys
    if section == "settings":
        if name == "library":
            _set_library(ctx, db, value)
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


def _set_check(ctx: app.Context, check_name: str, name: str, value: str):
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


def _interactive_config(ctx: app.Context, db: sqlite3.Connection):
    done = False
    while not done:
        option = choice(
            message="select an option",
            options=[
                ("settings", "settings"),
                ("enable", "enable/disable checks"),
                ("configure", "configure checks"),
                ("exit", "exit"),
            ],
        )
        match option:
            case "settings":
                _configure_settings(ctx, db)
            case "enable":
                enabled_checks = checkboxlist_dialog(
                    "enable selected checks",
                    values=[(v, v) for v in sorted(ctx.config.checks.keys())],
                    default_values=[c for c, cfg in ctx.config.checks.items() if cfg["enabled"]],
                ).run()
                if enabled_checks is not None:  # pyright: ignore[reportUnnecessaryComparison]
                    _set_enabled_checks(ctx, db, set(enabled_checks))
            case "configure":
                configurable = list((check_name, check_name) for check_name, config in ctx.config.checks.items() if len(config) > 1)
                while option and option != "back":
                    option = choice(message="select a check to configure", options=configurable + [("back", "<< go back")])
                    if option and option != "back":
                        _configure_check(ctx, db, option)
            case _:
                done = True


def _configure_settings(ctx: app.Context, db: sqlite3.Connection):
    option = "_"
    while option and option != "back":
        option = choice(
            message="edit a setting",
            options=[
                ("library", f"library ({str(ctx.config.library)})"),
                ("rescan", f"rescan ({ctx.config.rescan})"),
                ("tagger", f"tagger ({ctx.config.tagger if ctx.config.tagger else 'not set'})"),
                (
                    "open_folder_command",
                    f"open_folder_command ({ctx.config.open_folder_command if ctx.config.open_folder_command else 'not set'})",
                ),
                ("back", "<< go back"),
            ],
        )
        if option and option != "back":
            _configure_setting(ctx, db, option)


def _configure_setting(ctx: app.Context, db: sqlite3.Connection, setting: Literal["library", "rescan", "tagger", "open_folder_command"]):
    match setting:
        case "library":
            path_completer = PathCompleter()
            new_library = prompt("Location/path of the music library: ", completer=path_completer, default=str(ctx.config.library))
            _set_library(ctx, db, new_library)
        case "rescan":
            options = [(opt, opt.value) for opt in RescanOption]
            option = choice(message="select when to rescan the library", options=options, default=ctx.config.rescan.value)
            ctx.config.rescan = RescanOption(option)
            configuration.save(db, ctx.config)
        case "tagger":
            ctx.config.tagger = prompt("Command to run external tagger: ", default=ctx.config.tagger)
            configuration.save(db, ctx.config)
        case "open_folder_command":
            ctx.config.open_folder_command = prompt("Command to open a folder: ", default=ctx.config.open_folder_command)
            configuration.save(db, ctx.config)


def _set_library(ctx: app.Context, db: sqlite3.Connection, new_library: str):
    if new_library and Path(new_library).is_dir():
        ctx.config.library = Path(new_library)
        configuration.save(db, ctx.config)
    else:
        ctx.console.print("Error: library must be a directory that exists and is accessible")


def _configure_check(ctx: app.Context, db: sqlite3.Connection, check_name: str):
    option = "_"
    while option and option != "back":
        config = ctx.config.checks[check_name]
        options = [(k, f"{k} ({str(v)})") for k, v in config.items() if k != "enabled"]
        option = choice(message=f"configuring check {check_name}", options=options + [("back", "<< go back")])
        if option == "back":
            continue
        elif isinstance(config[option], str):
            config[option] = prompt(f"New value for {option}: ", default=str(config[option]))
        elif isinstance(config[option], bool):
            config[option] = choice(
                message=f"Enter a new bool value for {option}", options=[(True, "True"), (False, "False")], default=config[option]
            )
        elif isinstance(config[option], int):
            config[option] = IntPrompt.ask(f"Enter a new int value for {option}", default=config[option])
        elif isinstance(config[option], float):
            config[option] = FloatPrompt.ask(f"Enter a new float value for {option}", default=config[option])
        elif isinstance(config[option], list):
            default_items = str(",".join(config[option]))  # type: ignore
            items = prompt(f"Enter new values separated by comma for {option}: ", default=default_items)
            config[option] = items.split(",")
        configuration.save(db, ctx.config)


def _set_enabled_checks(ctx: app.Context, db: sqlite3.Connection, enabled_checks: set[str]):
    changed = False
    for check_name, config in ctx.config.checks.items():
        value = check_name in enabled_checks
        if config["enabled"] != value:
            config["enabled"] = value
            changed = True
    if changed:
        configuration.save(db, ctx.config)
