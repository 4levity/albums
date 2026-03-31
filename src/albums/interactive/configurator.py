from prompt_toolkit.shortcuts import checkboxlist_dialog, choice

from ..app import Context
from .setup_check import configure_check, set_enabled_checks
from .setup_destination import configure_destinations
from .setup_settings import configure_settings


def interactive_config(ctx: Context):
    done = False
    while not done:
        option = choice(
            message="select an option",
            options=[
                ("settings", "settings"),
                ("enable", "enable/disable checks"),
                ("configure", "configure checks"),
                ("destinations", "configure sync destinations"),
                ("exit", "exit"),
            ],
        )
        match option:
            case "settings":
                configure_settings(ctx)
            case "enable":
                enabled_checks = checkboxlist_dialog(
                    "enable selected checks",
                    values=[(v, v) for v in sorted(ctx.config.checks.keys())],
                    default_values=[c for c, cfg in ctx.config.checks.items() if cfg["enabled"]],
                ).run()
                if enabled_checks is not None:  # pyright: ignore[reportUnnecessaryComparison]
                    set_enabled_checks(ctx, set(enabled_checks))
            case "configure":
                configurable = list((check_name, check_name) for check_name, config in ctx.config.checks.items() if len(config) > 1)
                while option and option != "back":
                    option = choice(message="select a check to configure", options=configurable + [("back", "<< go back")])
                    if option and option != "back":
                        configure_check(ctx, option)
            case "destinations":
                configure_destinations(ctx)
            case _:
                done = True
