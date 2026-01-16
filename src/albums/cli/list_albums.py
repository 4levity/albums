import click
from functools import reduce
import humanize
from json import dumps

from .. import app
from ..types import Album


@click.command("list", help="print matching albums")
@click.option("--json", is_flag=True, help="output all stored details in JSON")
@app.pass_context
def list_albums(ctx: app.Context, json):
    total_size = 0
    count = 0
    if json:
        click.echo("[", nl=False)
    first = True
    album: Album
    for album in ctx.select_albums(json):
        tracks_size = reduce(lambda sum, track: sum + track.file_size, album.tracks, 0)
        if json:
            if first:
                first = False
            else:
                click.echo(",")
            click.echo(dumps(album.to_dict()), nl=False)
        else:
            click.echo(f"album: {album.path} ({humanize.naturalsize(tracks_size, binary=True)})")
        total_size += tracks_size
        count += 1
    if json:
        click.echo("]")  # TODO don't put a comma on the last
    elif count > 0:
        click.echo(f"total size: {humanize.naturalsize(total_size, binary=True)}")
    else:
        click.echo("no matching albums")
