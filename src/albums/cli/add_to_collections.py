import click
from .. import database


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
