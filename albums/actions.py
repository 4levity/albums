import click
from functools import reduce
import humanize
from albums import checks, database


@click.command("list", help="print matching album paths")
@click.option("--details", is_flag=True, help="print all details of each album")
@click.pass_context
def list_albums(ctx: click.Context, details):
    albums = ctx.obj["SELECT_ALBUMS"]()
    formatter = (lambda a, sz: a) if details else (lambda a, sz: f"album: {a['path']} ({sz})")
    total_size = 0
    for album in albums:
        tracks_size = reduce(lambda sum, track: sum + track["FileSize"], album["tracks"], 0)
        click.echo(formatter(album, humanize.naturalsize(tracks_size, binary=True)))
        total_size += tracks_size
    if len(albums) > 0:
        click.echo(f"total size: {humanize.naturalsize(total_size, binary=True)}")
    else:
        click.echo("no matching albums")


@click.command("exceptions", help="list exceptions found in selected albums")
@click.pass_context
def list_exceptions(ctx: click.Context):
    checks_enabled = ctx.obj["CONFIG"].get("checks", {})
    albums = ctx.obj["SELECT_ALBUMS"]()
    issues = []
    for album in albums:
        album_issues = checks.check(album, checks_enabled, ctx.obj["ALBUMS_CACHE"])
        issues.extend([issue | {"path": album["path"]} for issue in album_issues])
    if len(issues) > 0:
        for issue in sorted(issues, key=lambda i: i["path"]):
            click.echo(f"{issue['message']} : {issue['path']}")
    else:
        click.echo("no exceptions found")


@click.command("add", help="add selected albums to collections")
@click.argument("collection_names", nargs=-1)
@click.pass_context
def add_to_collections(ctx: click.Context, collection_names):
    albums = ctx.obj["SELECT_ALBUMS"]()
    if len(albums) > 2 and not click.confirm(f"are you sure you want to add {len(albums)} albums to {collection_names}?"):
        ctx.abort()
    db = ctx.obj["DB_CONNECTION"]
    for album in albums:
        path = album["path"]
        album_collections = album.get("collections", [])
        changed = False
        for target_collection in collection_names:
            if target_collection in album_collections:
                click.echo(f"album {path} is already in collection {target_collection}")
            else:
                album_collections.append(target_collection)
                click.echo(f"added album {path} to collection {target_collection}")
                changed = True
        if changed:
            album["collections"] = album_collections
            database.update(db, album)


@click.command("remove", help="remove selected albums from collections")
@click.argument("collection_names", nargs=-1)
@click.pass_context
def remove_from_collections(ctx: click.Context, collection_names):
    albums = ctx.obj["SELECT_ALBUMS"]()
    db = ctx.obj["DB_CONNECTION"]
    for album in albums:
        path = album["path"]
        album_collections = album.get("collections", [])
        changed = False
        for target_collection in collection_names:
            if target_collection in album_collections:
                album_collections.remove(target_collection)
                click.echo(f"removed album {path} from collection {target_collection}")
                changed = True
            else:
                click.echo(f"album {path} was not in collection {target_collection}")  # filter may prevent this
        if changed:
            album["collections"] = album_collections
            database.update(db, album)
