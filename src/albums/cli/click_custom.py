from typing import Any

import rich_click as click


class InvisibleCountParam(click.ParamType):
    name = "count"

    def convert(self, value: Any, param: click.Parameter | None, ctx: click.Context | None):
        return click.INT.convert(value, param, ctx)

    def get_metavar(self, param: click.Parameter, ctx: click.Context):
        return ""
