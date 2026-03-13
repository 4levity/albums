import rich_click as click
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..app import Context
from ..checks.helpers import album_display_name
from ..types import AlbumCollectionAssociation, CollectionEntity
from .cli_context import pass_context, require_persistent_context


@click.command("add", help="add selected albums to collections")
@click.argument("collection_names", nargs=-1)
@pass_context
def collections_add(ctx: Context, collection_names: list[str]):
    require_persistent_context(ctx)
    with Session(ctx.db) as session:
        for album in ctx.select_album_entities(session):
            for target_collection in collection_names:
                if target_collection in album.collections:
                    ctx.console.print(f"album {album_display_name(ctx, album)} is already in collection {target_collection}", markup=False)
                else:
                    # It shouldn't be and isn't really necessary to look up the collection. But the association_proxy creator implementation in
                    # Album creates a duplicate CollectionEntity when the collection already exists, causing this warning:
                    # SAWarning: Identity map already had an identity for (<class 'albums.database.models.CollectionEntity'>, (1,), None), replacing it with newly flushed object.   Are there load operations occurring inside of an event handler within the flush?
                    collection = (
                        session.execute(select(CollectionEntity).where(CollectionEntity.collection_name == target_collection)).tuples().one_or_none()
                    )
                    if collection:
                        session.add(AlbumCollectionAssociation(album=album, collection=collection[0]))
                    else:
                        album.collections.append(target_collection)  # preferred way but causes sqlalchemy warning
                    ctx.console.print(f"added album {album_display_name(ctx, album)} to collection {target_collection}", markup=False)
        session.commit()
