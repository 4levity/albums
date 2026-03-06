import rich_click as click

from ..app import Context
from ..checks.helpers import album_display_name
from ..database import operations
from .cli_context import pass_context, require_persistent_context


@click.command("add", help="add selected albums to collections")
@click.argument("collection_names", nargs=-1)
@pass_context
def collections_add(ctx: Context, collection_names: list[str]):
    require_persistent_context(ctx)
    for album in ctx.select_albums(False):
        changed = False
        for target_collection in collection_names:
            if target_collection in album.collections:
                ctx.console.print(f"album {album_display_name(ctx, album)} is already in collection {target_collection}", markup=False)
            else:
                album.collections = list(album.collections) + [target_collection]
                ctx.console.print(f"added album {album_display_name(ctx, album)} to collection {target_collection}", markup=False)
                changed = True
        if changed:
            if album.album_id is None:
                raise ValueError(f"unexpected album.album_id=None for {album.path}")
            operations.update_collections(ctx.db, album.album_id, album.collections)
