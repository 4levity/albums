from typing import Collection

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import choice
from rich.prompt import FloatPrompt, IntPrompt

from ..app import Context
from ..database import db_config


def set_enabled_checks(ctx: Context, enabled_checks: Collection[str]):
    changed = False
    for check_name, config in ctx.config.checks.items():
        value = check_name in enabled_checks
        if config["enabled"] != value:
            config["enabled"] = value
            changed = True
    if changed:
        db_config.save(ctx.db, ctx.config)


def configure_check(ctx: Context, check_name: str):
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
        db_config.save(ctx.db, ctx.config)
