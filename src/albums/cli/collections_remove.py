import rich_click as click

from .. import app
from ..database import operations
from . import cli_context


@click.command("remove", help="remove selected albums from collections")
@click.argument("collection_names", nargs=-1)
@cli_context.pass_context
def collections_remove(ctx: app.Context, collection_names: list[str]):
    if not ctx.db:
        raise ValueError("remove requires database connection")

    for album in ctx.select_albums(False):
        path = album.path
        album_collections = album.collections if album.collections else []
        changed = False
        for target_collection in collection_names:
            if target_collection in album_collections:
                album_collections.remove(target_collection)
                ctx.console.print(f"removed album {path} from collection {target_collection}", markup=False)
                changed = True
            else:
                ctx.console.print(f"album {path} was not in collection {target_collection}", markup=False)  # filter may prevent this
        if changed:
            if album.album_id is None:
                raise ValueError(f"unexpected album.album_id=None for {album.path}")
            album.collections = album_collections
            operations.update_collections(ctx.db, album.album_id, album.collections)
