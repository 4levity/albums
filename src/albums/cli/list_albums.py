import rich_click as click
from functools import reduce
import humanize
from json import dumps

from .. import app
from ..types import Album
from . import cli_context


@click.command("list", help="print matching albums")
@click.option("--json", is_flag=True, help="output all stored details in JSON")
@cli_context.pass_context
def list_albums(ctx: app.Context, json):
    total_size = 0
    count = 0
    if json:
        ctx.console.print("[")
    first = True
    album: Album
    for album in ctx.select_albums(json):
        tracks_size = reduce(lambda sum, track: sum + track.file_size, album.tracks, 0)
        if json:
            if first:
                first = False
            else:
                ctx.console.print(",")

            if ctx.console.is_terminal:
                ctx.console.print_json(dumps(album.to_dict()))  # pretty for terminal
            else:
                ctx.console.print(dumps(album.to_dict()), end="")  # otherwise compact
        else:
            ctx.console.print(f"{album.path} [bold]{humanize.naturalsize(tracks_size, binary=True)}", highlight=False)
        total_size += tracks_size
        count += 1
    if json:
        ctx.console.print("]")
    elif count > 0:
        ctx.console.print(f"total size: {humanize.naturalsize(total_size, binary=True)}")
    else:
        ctx.console.print("no matching albums")
