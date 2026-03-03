from pathlib import Path

import rich_click as click
from prompt_toolkit import choice
from prompt_toolkit.shortcuts import confirm
from rich.markup import escape

from ..app import Context
from ..checks.checker import Checker
from ..library.import_album import import_album, make_library_paths
from ..library.scanner import scan
from .cli_context import enter_folder_context, pass_context, require_persistent_context


@click.command("import", help="check album in a folder, copy to library if it passes")
@click.argument("scan_folder", required=True)
@click.option("--extra", "-x", is_flag=True, help="copy extra files not scanned by albums")
@click.option("--recursive", "-r", is_flag=True, help="copy folders (implies --extra)")
@click.option("--automatic", "-a", is_flag=True, help="if there is an automatic fix, do it WITHOUT ASKING")
@pass_context
def import_command(ctx: Context, extra: bool, recursive: bool, automatic: bool, scan_folder: str):
    _db = require_persistent_context(ctx)
    enter_folder_context(ctx, scan_folder, [], False)
    (albums_total, _) = scan(ctx)
    if albums_total == 0:
        ctx.console.print(f"Album not found at {escape(scan_folder)}")
        raise SystemExit(1)
    if albums_total > 1:
        ctx.console.print(f"More than one album found at {escape(scan_folder)}")
        raise SystemExit(1)

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
        album = list(ctx.select_albums(True))[0]
        source_path = Path(scan_folder) / album.path
        library_paths = make_library_paths(ctx, album)
        options = [(album_path, f">> Copy to {album_path}") for album_path in library_paths] + [("", ">> Cancel")]
        library_path = choice(message=f"Ready to copy from {source_path}", options=options)
        if library_path:
            import_album(ctx, source_path, library_path, album, extra, recursive)
