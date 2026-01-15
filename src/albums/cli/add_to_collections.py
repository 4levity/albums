import click
import albums.database.operations


@click.command("add", help="add selected albums to collections")
@click.argument("collection_names", nargs=-1)
@click.pass_context
def add_to_collections(ctx: click.Context, collection_names):
    for album in ctx.obj["SELECT_ALBUMS"](False):
        path = album.path
        changed = False
        for target_collection in collection_names:
            if target_collection in album.collections:
                click.echo(f"album {path} is already in collection {target_collection}")
            else:
                album.collections.append(target_collection)
                click.echo(f"added album {path} to collection {target_collection}")
                changed = True
        if changed:
            albums.database.operations.update_collections(ctx.obj["DB_CONNECTION"], album.album_id, album.collections)
