from datetime import UTC, datetime
from functools import reduce
from json import dumps

import humanize
import rich_click as click
from rich.table import Table
from sqlalchemy.orm import Session

from ..app import Context
from ..checks.helpers import album_display_name
from .cli_context import pass_context, require_real_context


@click.command("list", help="print matching albums", add_help_option=False)
@click.option("--json", "-j", is_flag=True, help="output all stored details in JSON")
@click.help_option("--help", "-h", help="show this message and exit")
@pass_context
def list_albums(ctx: Context, json: bool):
    require_real_context(ctx)
    total_size = 0
    total_length = 0
    table = Table("path in library", "tracks", "length", "size", "added", "changed")
    with Session(ctx.db) as session:
        for album in ctx.select_album_entities(session):
            tracks_size = reduce(lambda sum, track: sum + track.file_size, album.tracks, 0)
            tracks_length = reduce(
                lambda sum, track: sum + (track.stream.length if track.stream and hasattr(track.stream, "length") else 0), album.tracks, 0
            )
            if json:
                ctx.console.print("[" if total_size == 0 else ",")  # an album can't be 0 bytes
                if ctx.console.is_terminal:
                    ctx.console.print_json(dumps(album.to_dict()))  # pretty for terminal
                else:
                    ctx.console.print(dumps(album.to_dict()), end="", highlight=False, markup=False, soft_wrap=True)  # otherwise compact
            else:
                table.add_row(
                    album_display_name(ctx, album),
                    str(len(album.tracks)),
                    "{:02}:{:02}".format(*divmod(int(tracks_length) // 60, 60)),
                    humanize.naturalsize(tracks_size, binary=True),
                    datetime.fromtimestamp(album.created_at, UTC).astimezone().strftime("%x") if album.created_at else "[italic]not set[/italic]",
                    datetime.fromtimestamp(album.modified_at, UTC).astimezone().strftime("%x") if album.modified_at else "[italic]not set[/italic]",
                )
            total_size += tracks_size
            total_length += tracks_length
        if json:
            if total_size == 0:
                ctx.console.print("[]")
            else:
                ctx.console.print("]")
        else:
            ctx.console.print(table)
            ctx.console.print(f"total: {humanize.naturalsize(total_size, binary=True)}, length = {humanize.naturaldelta(total_length)}")
