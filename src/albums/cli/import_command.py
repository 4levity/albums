from pathlib import Path

import rich_click as click
from prompt_toolkit import choice
from prompt_toolkit.shortcuts import confirm
from rich.markup import escape
from sqlalchemy.orm import Session

from ..app import Context
from ..checks.checker import Checker
from ..library.import_album import import_album, make_library_paths
from ..library.scanner import scan
from .cli_context import enter_folder_context, pass_context, require_database, require_library, require_persistent_context


@click.command("import", help="check album in a folder, copy to library if it passes")
@click.argument("scan_folder", required=True)
@click.option("--extra", "-x", is_flag=True, help="copy extra files not scanned by albums")
@click.option("--recursive", "-r", is_flag=True, help="copy folders (implies --extra)")
@click.option("--automatic", "-a", is_flag=True, help="perform automatic fixes + import to default location")
@pass_context
def import_command(ctx: Context, extra: bool, recursive: bool, automatic: bool, scan_folder: str):
    require_persistent_context(ctx, "import")
    require_database(ctx, "import")
    require_library(ctx, "import")
    library = ctx.config.library
    enter_folder_context(ctx, scan_folder)
    (albums_total, _) = scan(ctx)
    if albums_total == 0:
        ctx.console.print(f"Album not found at {escape(scan_folder)}")
        raise SystemExit(1)
    if albums_total > 1:
        ctx.console.print(f"More than one album found at {escape(scan_folder)}")
        raise SystemExit(1)
    with Session(ctx.db) as session:
        album = next(ctx.select_album_entities(session))
        existing_confirmed = _check_existing_destination(ctx, make_library_paths(ctx, album))

    issues = 0
    quit = False
    checker = Checker(ctx, automatic, preview=False, fix=False, interactive=True, show_ignore_option=True)
    non_interactive_checker = Checker(ctx, False, False, False, False, False)
    while not quit and checker.run_enabled():
        ctx.console.print("Remaining issues:")
        issues = non_interactive_checker.run_enabled()
        if issues == 0:
            ctx.console.print("No issues")
        quit = issues == 0 or confirm("There are still issues, want to quit?")

    if not issues:
        with Session(ctx.db) as session:
            album = next(ctx.select_album_entities(session))
            library_paths = make_library_paths(ctx, album)
            if not existing_confirmed:  # check again in case tag fixes changed the destination paths
                _check_existing_destination(ctx, library_paths)
            source_path = Path(scan_folder) / album.path
            if automatic:
                path_in_library = library_paths[0]
            else:
                options = [(album_path, f">> Copy to: {album_path}") for album_path in library_paths] + [("", ">> Cancel")]
                path_in_library = choice(message=f"Ready to copy from {source_path}", options=options)
            if path_in_library:
                ctx.console.print(f"Import album from {source_path} to {str(library / path_in_library)}")
                import_album(ctx, source_path, path_in_library, album, extra, recursive)


def _check_existing_destination(ctx: Context, library_paths: list[str]) -> bool:
    root_ctx = ctx.parent if ctx.parent is not None else ctx
    # TODO check for duplicate album by tag values too
    existing = next((path for path in library_paths if (root_ctx.config.library / path).exists()), None)
    if existing is not None:
        ctx.console.print(f"This album appears to be in the library: [bold]{escape(existing)}[/bold]")
        if confirm("Are you sure you want to continue?"):
            return True
        else:
            raise SystemExit(1)
    return False
