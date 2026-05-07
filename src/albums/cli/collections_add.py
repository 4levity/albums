import rich_click as click
from sqlalchemy.orm import Session

from ..app import Context
from ..checks.helpers import album_display_name
from ..database.collections_by_name import collections_by_name
from ..types import AlbumCollectionAssociation
from .cli_context import pass_context, require_configured, require_persistent_context


@click.command("add", help="add selected albums to collections", add_help_option=False)
@click.argument("collection_names", nargs=-1)
@click.help_option("--help", "-h", help="show this message and exit")
@pass_context
def collections_add(ctx: Context, collection_names: list[str]):
    require_configured(ctx)
    require_persistent_context(ctx)
    if not collection_names:
        ctx.console.print("[bold]must specify at least one collection name[/bold]")
        raise SystemExit(1)

    with Session(ctx.db) as session:
        collections = collections_by_name(session, collection_names)
        for album in ctx.select_album_entities(session):
            for target_collection in collection_names:
                if target_collection in album.collections:
                    ctx.console.print(f"album {album_display_name(ctx, album)} is already in collection {target_collection}", markup=False)
                else:
                    # album.collections.append(target_collection) # see comment on collections_by_name for why we don't just do this
                    collection = collections[target_collection]
                    session.add(AlbumCollectionAssociation(album=album, collection=collection))
                    ctx.console.print(f"added album {album_display_name(ctx, album)} to collection {target_collection}", markup=False)
        session.commit()
