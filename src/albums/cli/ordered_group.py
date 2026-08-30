"""RichGroup subclass that lists commands in registration order instead of sorted order."""

from typing import override

from rich_click import Context, RichGroup


class OrderedGroup(RichGroup):
    """RichGroup that lists commands in registration order instead of alphabetical order."""

    @override
    def list_commands(self, ctx: Context):
        return list(self.commands.keys())
