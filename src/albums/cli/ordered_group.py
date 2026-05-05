from typing import override

from rich_click import Context, RichGroup


class OrderedGroup(RichGroup):
    @override
    def list_commands(self, ctx: Context):
        return list(self.commands.keys())
