import os
from pathlib import Path

import rich_click as click
from prompt_toolkit.shortcuts import confirm
from rich.markup import escape

from ..app import Context
from ..database import connection, db_config
from ..library import scanner
from .cli_context import PLATFORM_DIRS, pass_context


@click.command(help="initialize albums database")
@click.argument("library-path", required=False)
@pass_context
def init(ctx: Context, library_path: str | None):
    if ctx.db_path.exists():
        ctx.console.print(f"There is already a file at {escape(str(ctx.db_path))}", highlight=False)
        raise SystemExit(1)

    library = Path(library_path) if library_path else None
    if not library:
        if PLATFORM_DIRS.user_music_path.is_dir():
            if confirm(f"Library path not specified, do you want to use {str(PLATFORM_DIRS.user_music_path)} ?"):
                library = PLATFORM_DIRS.user_music_path
        if not library:
            ctx.console.print("Run [bold]albums init /path/to/library/[/bold] to specify the library location.")
            raise SystemExit(1)
    elif not library.is_dir():
        ctx.console.print(f"The library path must be a directory: {escape(str(library_path))}", highlight=False)
        raise SystemExit(1)

    if ctx.console.is_interactive and not confirm(f"No database file found at {str(ctx.db_path)}. Create this file?"):
        raise SystemExit(1)

    os.makedirs(ctx.db_path.parent, exist_ok=True)
    ctx.db = connection.open(ctx.db_path, echo=ctx.verbose > 1)
    try:
        ctx.config = db_config.load(ctx.db)
        ctx.config.library = library
        db_config.save(ctx.db, ctx.config)
        ctx.console.print(f"scanning library {escape(str(library))}", highlight=False)
        scanner.scan(ctx)
    finally:
        ctx.db.dispose()
