import click
from functools import reduce
import humanize


@click.command("list", help="print matching album paths")
@click.option("--details", is_flag=True, help="print all details of each album")
@click.pass_context
def list_albums(ctx: click.Context, details):
    formatter = (lambda a, sz: a) if details else (lambda a, sz: f"album: {a['path']} ({sz})")
    total_size = 0
    count = 0
    for album in ctx.obj["SELECT_ALBUMS"]():
        tracks_size = reduce(lambda sum, track: sum + track["FileSize"], album["tracks"], 0)
        click.echo(formatter(album, humanize.naturalsize(tracks_size, binary=True)))
        total_size += tracks_size
        count += 1
    if count > 0:
        click.echo(f"total size: {humanize.naturalsize(total_size, binary=True)}")
    else:
        click.echo("no matching albums")
