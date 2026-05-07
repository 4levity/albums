from typing import List, Tuple

import rich_click as click
from prompt_toolkit.shortcuts import checkboxlist_dialog
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..app import Context
from ..checks.helpers import album_display_name
from ..database.collections_by_name import collections_by_name
from ..types import Album, AlbumCollectionAssociation
from .cli_context import pass_context, require_configured, require_persistent_context


@click.command("select", help="interactively select albums to add to collections", add_help_option=False)
@click.argument("collection_names", nargs=-1)
@click.help_option("--help", "-h", help="show this message and exit")
@pass_context
def collections_select(ctx: Context, collection_names: list[str]):
    require_configured(ctx)
    require_persistent_context(ctx)
    if not collection_names:
        ctx.console.print("[bold]must specify at least one collection name[/bold]")
        raise SystemExit(1)

    with Session(ctx.db) as session:
        values: List[Tuple[int, str]] = []
        already_in_collections: List[int] = []
        for album in ctx.select_album_entities(session):
            values.append((album.album_id or 0, album.path))
            if all(c in album.collections for c in collection_names):
                already_in_collections.append(album.album_id or 0)
        selected_albums = checkboxlist_dialog(
            f"add albums to: {', '.join(sorted(collection_names))}", values=values, default_values=already_in_collections
        ).run()
        if selected_albums is not None:  # pyright: ignore[reportUnnecessaryComparison]
            collections = collections_by_name(session, collection_names)
            selected = set(selected_albums)
            previously_selected = set(already_in_collections)
            to_add = selected - previously_selected
            to_remove = previously_selected - selected
            for album_id in to_add:
                (album,) = session.execute(select(Album).where(Album.album_id == album_id)).tuples().one()
                for collection_name in collection_names:
                    if collection_name not in album.collections:
                        session.add(AlbumCollectionAssociation(album=album, collection=collections[collection_name]))
                        ctx.console.print(f"added album {album_display_name(ctx, album)} to collection {collection_name}", markup=False)
            for album_id in to_remove:
                (album,) = session.execute(select(Album).where(Album.album_id == album_id)).tuples().one()
                for collection_name in collection_names:
                    if collection_name in album.collections:
                        album.collections.remove(collection_name)
                        ctx.console.print(f"removed album {album_display_name(ctx, album)} from collection {collection_name}", markup=False)
        session.commit()
