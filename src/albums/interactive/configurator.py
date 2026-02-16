import sqlite3
from pathlib import Path
from typing import Literal

from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.shortcuts import checkboxlist_dialog, choice
from rich.prompt import FloatPrompt, IntPrompt

from ..app import Context
from ..database import configuration
from ..types import RescanOption


def interactive_config(ctx: Context, db: sqlite3.Connection):
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


def _configure_settings(ctx: Context, db: sqlite3.Connection):
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


def _configure_setting(ctx: Context, db: sqlite3.Connection, setting: Literal["library", "rescan", "tagger", "open_folder_command"]):
    match setting:
        case "library":
            path_completer = PathCompleter()
            new_library = prompt("Location/path of the music library: ", completer=path_completer, default=str(ctx.config.library))
            set_library(ctx, db, new_library)
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


def set_library(ctx: Context, db: sqlite3.Connection, new_library: str):
    if new_library and Path(new_library).is_dir():
        ctx.config.library = Path(new_library)
        configuration.save(db, ctx.config)
    else:
        ctx.console.print("Error: library must be a directory that exists and is accessible")


def _configure_check(ctx: Context, db: sqlite3.Connection, check_name: str):
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


def _set_enabled_checks(ctx: Context, db: sqlite3.Connection, enabled_checks: set[str]):
    changed = False
    for check_name, config in ctx.config.checks.items():
        value = check_name in enabled_checks
        if config["enabled"] != value:
            config["enabled"] = value
            changed = True
    if changed:
        configuration.save(db, ctx.config)
