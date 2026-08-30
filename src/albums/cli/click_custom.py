"""Custom click parameter types for the albums CLI."""

from typing import Any

import rich_click as click


class InvisibleCountParam(click.ParamType[int]):
    """Click count parameter that hides its metavar, so the option shows as bare ``-v``/``-vv`` in help output."""

    name = "count"

    def convert(self, value: Any, param: click.Parameter | None, ctx: click.Context | None):
        return click.INT.convert(value, param, ctx)

    def get_metavar(self, param: click.Parameter, ctx: click.Context):
        return ""
