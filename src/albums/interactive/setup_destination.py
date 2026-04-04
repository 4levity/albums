import platform
from pathlib import Path
from string import Template

from prompt_toolkit import choice, prompt
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.shortcuts import confirm
from rich.markup import escape
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..app import Context
from ..config import SyncDestination
from ..database import db_config
from ..library.paths import show_template_path_help
from ..tagger.folder import AUDIO_FILE_SUFFIXES
from ..types import CollectionEntity


def configure_destinations(ctx: Context):
    option = "_"
    while option and option != "back":
        options: list[tuple[str, str]] = [(str(ix), str(dest)) for ix, dest in enumerate(ctx.config.sync_destinations)]
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
            dest = SyncDestination(_get_collection(ctx), Path(path_root))

            ix = len(ctx.config.sync_destinations)
            ctx.config.sync_destinations.append(dest)
            _configure_destination(ctx, ix)
        elif option != "back":
            _configure_destination(ctx, int(option))


def _get_destination_root(ctx: Context, default: Path | None = None) -> Path | None:
    path_completer = PathCompleter()
    dest_str = prompt("Path to the root of the sync destination: ", completer=path_completer, default=str(default) if default else "")
    dest_path = Path(dest_str)
    if not dest_path.is_absolute():
        ctx.console.print(f"[bold red]Error:[/bold red] must be an absolute path{' with drive letter' if platform.system() == 'Windows' else ''}")
        return None
    if dest_path.exists() and not dest_path.is_dir():
        ctx.console.print("[bold red]Error:[/bold red] the destination cannot be a file")
        return None
    if not dest_path.is_dir() and ctx.console.is_interactive and not confirm("The directory doesn't exist. Are you sure you want to use it?"):
        ctx.console.print("Canceled.")
        return None
    return dest_path


def _get_collection(ctx: Context, default: str = "") -> str:
    with Session(ctx.db) as session:
        collection_names = [
            c.collection_name for (c,) in session.execute(select(CollectionEntity).order_by(CollectionEntity.collection_name)).tuples()
        ]
    options = [(name, name) for name in collection_names] + [("", ">> Create a new collection")]
    default_option = default if default else (collection_names[0] if len(collection_names) else "")
    option = choice(message="Which albums collection to use for this sync destination?", options=options, default=default_option)
    if option:
        return option
    while not (option := prompt("Collection name: ")):
        pass
    match = next((name for name in collection_names if name.lower() == option.lower()), None)
    if match:
        option = match
        ctx.console.print("Using existing collection")
    ctx.console.print(f"To use this destination, add some albums to this collection: {option}")
    return option


def _configure_destination(ctx: Context, destination_ix: int):
    dest = ctx.config.sync_destinations[destination_ix]
    option = "_"
    while option and option not in {"save", "delete", "cancel"}:
        options: list[tuple[str, str]] = [
            ("collection", f"Collection: {dest.collection}"),
            ("path_root", f"Destination path root: {escape(str(dest.path_root))}"),
            ("relpath_template_artist", f"Album path template (albums with artist) or blank=same: {dest.relpath_template_artist.template}"),
            ("relpath_template_compilation", f"Album path template (compilations) or blank=same: {dest.relpath_template_compilation.template}"),
            ("allow_file_types", f"Music file types allowed, or blank=any: {','.join(dest.allow_file_types)}"),
            ("max_kbps", f"Max audio kbps or 0 for none: {dest.max_kbps}"),
            ("convert_profile", f"If wrong type or over max kbps, use transcode options: {dest.convert_profile}"),
            ("save", ">> Save"),
            ("delete", ">> Delete this destination"),
            ("cancel", ">> Cancel"),
        ]
        option = choice(message=f"Editing destination {str(dest)}", options=options)
        if option == "collection":
            dest.collection = _get_collection(ctx, dest.collection)
        elif option == "path_root":
            value = _get_destination_root(ctx, dest.path_root)
            if value is not None:
                dest.path_root = value
        elif option == "relpath_template_artist":
            show_template_path_help(ctx)
            dest.relpath_template_artist = Template(
                prompt("Template for default (not compilation) destination path: ", default=dest.relpath_template_artist.template)
            )
        elif option == "relpath_template_compilation":
            show_template_path_help(ctx)
            dest.relpath_template_compilation = Template(
                prompt("Template for compilation destination path: ", default=dest.relpath_template_compilation.template)
            )
        elif option == "allow_file_types":
            ctx.console.print(f"Known audio file types: {', '.join(suffix[1:] for suffix in AUDIO_FILE_SUFFIXES)}")
            file_types = prompt(
                "Enter destination allowed audio types separated by commas or empty to allow all: ", default=",".join(dest.allow_file_types)
            ).split(",")
            if any(f".{str.lower(file_type)}" not in AUDIO_FILE_SUFFIXES for file_type in file_types):
                ctx.console.print("Invalid file type")
                continue
            dest.allow_file_types = [str.lower(file_type) for file_type in file_types]
        elif option == "max_kbps":
            while not str.isdecimal(
                max_kbps := prompt("Max average bitrate in kbps (kilobytes per second) or 0 to allow all: ", default=str(dest.max_kbps))
            ):
                pass
            dest.max_kbps = int(max_kbps)
        elif option == "convert_profile":
            ctx.console.print()
            ctx.console.print("Profile is formatted as: [bold]\\[FFMPEG_OUTPUT_OPTIONS] FILE_TYPE[/bold]")
            ctx.console.print("Example (320kbps MP3): [bold]-b:a 320k mp3[/bold]", highlight=False)
            conversion_profile = prompt("Conversion profile: ", default=dest.convert_profile)
            file_type = conversion_profile.split(" ")[-1]
            if f".{file_type}" in AUDIO_FILE_SUFFIXES:
                dest.convert_profile = str.lower(conversion_profile)
            else:
                ctx.console.print(f"Error: unknown file type {file_type}")

    if option in {"save", "delete"}:
        if option == "delete":
            del ctx.config.sync_destinations[destination_ix]
        db_config.save(ctx.db, ctx.config)
