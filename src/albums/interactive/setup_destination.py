from prompt_toolkit import choice
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..app import Context
from ..types import CollectionEntity, SyncDestination


def configure_destinations(ctx: Context):
    option = "_"
    while option and option != "back":
        with Session(ctx.db) as session:
            options: list[tuple[str, str]] = [
                (str(d.destination_id), _describe(d))
                for (d,) in session.execute(
                    select(SyncDestination)
                    .join(CollectionEntity, SyncDestination.collection_id == CollectionEntity.collection_id)
                    .order_by(CollectionEntity.collection_name)
                ).tuples()
            ]
        options.extend(
            [
                ("new", ">> Create a new sync destination"),
                ("back", "<< go back"),
            ]
        )
        option = choice(message="Select a sync destination", options=options)
        if option == "new":
            pass  # TODO create new
        elif option != "back":
            _configure_destination(ctx, int(option))


def _configure_destination(ctx: Context, destination_id: int):
    with Session(ctx.db) as session:
        (dest,) = session.execute(select(SyncDestination).filter(SyncDestination.destination_id == destination_id)).tuples().one()
        option = "_"
        while option and option not in {"save", "delete", "cancel"}:
            options: list[tuple[str, str]] = [
                # TODO configure fields
                ("save", "save"),
                ("delete", "delete this destination"),
                ("cancel", "cancel"),
            ]
            option = choice(message=f"editing destination {_describe(dest)}", options=options)
            if option == "":
                pass
        if option == "save":
            session.commit()
        elif option == "delete":
            pass


def _describe(d: SyncDestination) -> str:
    return f"{d.collection.collection_name} -> {d.path_root}"
