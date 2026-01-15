import click

import albums.database.operations
from ..context import AppContext, pass_app_context


@click.command("remove", help="remove selected albums from collections")
@click.argument("collection_names", nargs=-1)
@pass_app_context
def remove_from_collections(ctx: AppContext, collection_names):
    for album in ctx.select_albums(False):
        path = album.path
        album_collections = album.collections if album.collections else []
        changed = False
        for target_collection in collection_names:
            if target_collection in album_collections:
                album_collections.remove(target_collection)
                click.echo(f"removed album {path} from collection {target_collection}")
                changed = True
            else:
                click.echo(f"album {path} was not in collection {target_collection}")  # filter may prevent this
        if changed:
            album.collections = album_collections
            albums.database.operations.update_collections(ctx.db, album.album_id, album.collections)
