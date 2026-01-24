import rich_click as click

import albums.database.operations
from .. import app
from . import cli_context


@click.command("add", help="add selected albums to collections")
@click.argument("collection_names", nargs=-1)
@cli_context.pass_context
def collections_add(ctx: app.Context, collection_names):
    for album in ctx.select_albums(False):
        path = album.path
        changed = False
        for target_collection in collection_names:
            if target_collection in album.collections:
                ctx.console.print(f"album {path} is already in collection {target_collection}", markup=False)
            else:
                album.collections.append(target_collection)
                ctx.console.print(f"added album {path} to collection {target_collection}", markup=False)
                changed = True
        if changed:
            albums.database.operations.update_collections(ctx.db, album.album_id, album.collections)
