import rich_click as click
from rich.markup import escape
from rich.prompt import Confirm

from ..app import Context
from ..checks.checker import Checker
from ..library import scanner
from .cli_context import enter_folder_context, pass_context, require_persistent_context


@click.command("import", help="check album in a folder, copy to library if it passes")
@click.argument("album_folder", required=True)
@click.option("--extra", "-x", is_flag=True, help="copy extra files not scanned by albums")
@click.option("--recursive", "-r", is_flag=True, help="copy folders (implies --extra)")
@click.option("--automatic", "-a", is_flag=True, help="if there is an automatic fix, do it WITHOUT ASKING")
@click.option("--preview", "-p", is_flag=True, help="preview the automatic fixes that would be made with -a")
@click.option("--fix", "-f", is_flag=True, help="prompt when there is a selectable fix available")
@click.option("--interactive", "-i", is_flag=True, help="ask what to do even if the only options are manual (implies -f)")
@pass_context
def import_album(ctx: Context, extra: bool, recursive: bool, automatic: bool, preview: bool, fix: bool, interactive: bool, album_folder: str):
    _db = require_persistent_context(ctx)
    ctx.console.print("import")
    enter_folder_context(ctx, album_folder, [], False)
    (albums_total, _) = scanner.scan(ctx)
    if albums_total == 0:
        ctx.console.print(f"Album not found at {escape(album_folder)}")
        raise SystemExit(1)
    if albums_total > 1:
        ctx.console.print(f"More than one album found at {escape(album_folder)}")
        raise SystemExit(1)

    ctx.console.print(f"found {albums_total} album")
    issues = 0
    quit = False
    checker = Checker(ctx, automatic, preview, fix, interactive, show_ignore_option=True)
    while not quit and (issues := checker.run_enabled()):
        quit = Confirm.ask("there are still problems, quit?", console=ctx.console)

    if issues:
        ctx.console.print("not copying")
    else:
        ctx.console.print(f"would copy {escape(album_folder)}")
