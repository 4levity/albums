import rich_click as click

from ..app import Context
from ..database import operations
from . import cli_context


@click.command("add", help="add selected albums to collections")
@click.argument("collection_names", nargs=-1)
@cli_context.pass_context
def collections_add(ctx: Context, collection_names: list[str]):
    if not ctx.db:
        raise ValueError("add requires database connection")

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
            if album.album_id is None:
                raise ValueError(f"unexpected album.album_id=None for {album.path}")
            operations.update_collections(ctx.db, album.album_id, album.collections)
