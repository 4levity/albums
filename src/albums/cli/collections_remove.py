import rich_click as click
from sqlalchemy.orm import Session

from ..app import Context
from ..checks.helpers import album_display_name
from .cli_context import pass_context, require_configured, require_persistent_context


@click.command("remove", help="remove selected albums from collections", add_help_option=False)
@click.argument("collection_names", nargs=-1)  # pyright: ignore[reportUnknownMemberType]
@click.help_option("--help", "-h", help="show this message and exit")  # pyright: ignore[reportUnknownMemberType]
@pass_context
def collections_remove(ctx: Context, collection_names: list[str]):
    require_configured(ctx)
    require_persistent_context(ctx)
    with Session(ctx.db) as session:
        for album in ctx.select_album_entities(session):
            for target_collection in collection_names:
                if target_collection in album.collections:
                    album.collections.remove(target_collection)
                    ctx.console.print(f"removed album {album_display_name(ctx, album)} from collection {target_collection}", markup=False)
                else:
                    ctx.console.print(
                        f"album {album_display_name(ctx, album)} was not in collection {target_collection}", markup=False
                    )  # filter may prevent this
        session.commit()
