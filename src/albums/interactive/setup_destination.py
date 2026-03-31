from pathlib import Path

from prompt_toolkit import choice, prompt
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.shortcuts import confirm
from rich.markup import escape
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
            path_root = _get_destination_root(ctx)
            if not path_root:
                continue
            with Session(ctx.db) as session:
                collection_id = _get_collection_id(ctx, session)
                dest = SyncDestination(collection_id=collection_id, path_root=path_root)
                session.add(dest)
                session.commit()
                if dest.destination_id is None:
                    raise RuntimeError("failed to save destination")
                destination_id = dest.destination_id
            _configure_destination(ctx, destination_id)
        elif option != "back":
            _configure_destination(ctx, int(option))


def _get_destination_root(ctx: Context, default: str = "") -> str | None:
    path_completer = PathCompleter()
    dest_str = prompt("Path to the root of the sync destination: ", completer=path_completer, default=default)
    dest_path = Path(dest_str)
    if dest_path.exists() and not dest_path.is_dir():
        ctx.console.print("[bold red]Error:[/bold red] the destination cannot be a file")
        return None
    if not dest_path.is_dir() and ctx.console.is_interactive and not confirm("The directory doesn't exist. Are you sure you want to use it?"):
        ctx.console.print("Canceled.")
        return None
    dest_str = str(dest_path)
    if not dest_str or dest_str == ".":
        return None
    return dest_str


def _get_collection_id(ctx: Context, session: Session, default_id: int | None = None) -> int:
    options: list[tuple[int, str]] = [
        (c.collection_id or 0, c.collection_name)
        for (c,) in session.execute(select(CollectionEntity).order_by(CollectionEntity.collection_name)).tuples()
    ]
    options.append((0, ">> Create a new collection"))
    option = choice(message="", options=options)
    if option:
        return option
    while not (name := prompt("New collection name: ")):
        pass
    new_collection = CollectionEntity(collection_name=name)
    session.add(new_collection)
    session.flush()
    if new_collection.collection_id is None:
        raise RuntimeError("failed to save new collection")  # shouldn't happen, just for type
    ctx.console.print(f"Created new collection: {escape(name)}")
    return new_collection.collection_id


def _configure_destination(ctx: Context, destination_id: int):
    with Session(ctx.db) as session:
        (dest,) = session.execute(select(SyncDestination).filter(SyncDestination.destination_id == destination_id)).tuples().one()
        option = "_"
        while option and option not in {"save", "delete", "cancel"}:
            options: list[tuple[str, str]] = [
                ("collection", f"Collection: {dest.collection.collection_name}"),
                ("path_root", f"Destination path root: {escape(dest.path_root)}"),
                ("relpath_template_artist", f"Album path template (albums with artist) or blank=same: {dest.relpath_template_artist}"),
                ("relpath_template_compilation", f"Album path template (compilations) or blank=same: {dest.relpath_template_compilation}"),
                ("allow_file_types", f"Music file types allowed, or blank=any: {','.join(dest.allow_file_types)}"),
                ("convert_file_type", f"Music file type to convert to: {dest.convert_file_type}"),
                ("max_kbps", f"Max audio kbps or 0 for none: {dest.max_kbps}"),
                ("save", ">> Save"),
                ("delete", ">> Delete this destination"),
                ("cancel", ">> Cancel"),
            ]
            option = choice(message=f"Editing destination {_describe(dest)}", options=options)
            if option == "collection":
                dest.collection_id = _get_collection_id(ctx, session, dest.collection_id)
            elif option == "path_root":
                value = _get_destination_root(ctx, dest.path_root)
                if value is not None:
                    dest.path_root = value
            elif option == "relpath_template_artist":
                pass
            elif option == "relpath_template_compilation":
                pass
            elif option == "allow_file_types":
                pass
            elif option == "convert_file_type":
                pass
            elif option == "max_kbps":
                pass

        if option == "save":
            session.commit()
        elif option == "delete":
            pass


def _describe(d: SyncDestination) -> str:
    return f"{d.collection.collection_name} -> {d.path_root}"
