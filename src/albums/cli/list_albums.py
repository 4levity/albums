from datetime import UTC, datetime
from functools import reduce
from json import dumps
from typing import Callable, List, Tuple

import humanize
import rich_click as click
from rich.table import Table
from sqlalchemy.orm import Session

from ..app import Context
from ..checks.helpers import album_display_name
from .cli_context import pass_context, require_real_context


@click.command("list", help="print matching albums", add_help_option=False)
@click.option("--json", "-j", is_flag=True, help="output all stored details in JSON")
@click.option("--order", "-o", metavar="COLUMN", help="order by specified column name (not with --json)")
@click.option("--reverse", "-r", is_flag=True, help="reverse sort order")
@click.help_option("--help", "-h", help="show this message and exit")
@pass_context
def list_albums(ctx: Context, json: bool, order: str, reverse: bool):
    require_real_context(ctx)

    columns: List[Tuple[str, Callable[[str | int], str]]] = [
        ("path", lambda p: str(p)),
        ("tracks", lambda len_tracks: str(len_tracks)),
        ("length", lambda tracks_length: "{:02}:{:02}".format(*divmod(int(tracks_length) // 60, 60))),
        ("size", lambda tracks_size: humanize.naturalsize(tracks_size, binary=True)),
        ("added", _render_date),
        ("changed", _render_date),
    ]
    column_names = [name for name, _ in columns]
    if json and (order or reverse):
        ctx.console.print("[bold]cannot combine --json option with --order or --reverse[/bold]")
        raise SystemExit(1)
    if order and order not in column_names:
        ctx.console.print(f"[bold]invalid column name for --order (must be one of {', '.join(column_names)})[/bold]")
        raise SystemExit(1)
    if reverse and not order:
        order = columns[0][0]
    sort_column_ix = column_names.index(order) if order else 0
    total_size = 0
    total_length = 0
    table = Table(*(name for name, _ in columns))
    rows: List[Tuple[str | int, ...]] = []
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
                row = (album_display_name(ctx, album), len(album.tracks), int(tracks_length), tracks_size, album.created_at, album.modified_at)
                if order:
                    rows.append(row)
                else:
                    table.add_row(*(render(row[ix]) for ix, (_, render) in enumerate(columns)))
            total_size += tracks_size
            total_length += tracks_length
        if json:
            if total_size == 0:
                ctx.console.print("[]")
            else:
                ctx.console.print("]")
        else:
            if order:
                for row in sorted(rows, key=lambda row: row[sort_column_ix], reverse=reverse):
                    table.add_row(*(render(row[ix]) for ix, (_, render) in enumerate(columns)))
            ctx.console.print(table)
            ctx.console.print(f"total: {humanize.naturalsize(total_size, binary=True)}, length = {humanize.naturaldelta(total_length)}")


def _render_date(timestamp: str | int):
    if timestamp:
        return datetime.fromtimestamp(int(timestamp), UTC).astimezone().strftime("%Y-%m-%d")
    return "[italic]not set[/italic]"
