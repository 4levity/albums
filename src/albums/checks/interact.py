import logging
import os
from pathlib import Path
import platform
import subprocess
from rich.markup import escape
from rich.prompt import Confirm
from rich.table import Table

import albums.database.operations
from .. import app
from ..types import Album
from .base_check import ProblemCategory, CheckResult
from simple_term_menu import TerminalMenu

logger = logging.getLogger(__name__)


def interact(ctx: app.Context, check_name: str, check_result: CheckResult, album: Album) -> bool:
    # if there is a fixer, offer the options it provides
    # always offer these options:
    #  - do nothing
    #  - ignore this check for this album
    #  - browse folder (if appropriate problem type)
    #  - run tagger (if configured + appropriate problem type)
    # if there is an automatic fix option, it is the default, otherwise do nothing is the default

    fixer = check_result.fixer
    done = False  # allow user to start over if canceled by accident or not confirmed
    maybe_changed = False

    tagger_config = ctx.config.get("options", {}).get("tagger")
    tagger = str(tagger_config) if check_result.category == ProblemCategory.TAGS and tagger_config else None

    OPTION_FREE_TEXT = ">> Enter Text"
    OPTION_RUN_TAGGER = f">> Edit tags with {tagger}"
    OPTION_OPEN_FOLDER = ">> Open folder and see all files"
    OPTION_DO_NOTHING = ">> Do nothing"
    OPTION_IGNORE_CHECK = ">> Ignore this check for this album"

    options: list[str] = []
    if fixer:
        options.extend([opt for opt in fixer.options if opt not in [OPTION_FREE_TEXT, OPTION_RUN_TAGGER, OPTION_DO_NOTHING]])
    if fixer and fixer.option_free_text:
        options.append(OPTION_FREE_TEXT)
    options.append(OPTION_IGNORE_CHECK)
    do_nothing_index = len(options)
    options.append(OPTION_DO_NOTHING)
    if tagger:
        options.append(OPTION_RUN_TAGGER)
    # if check_result.category != ProblemCategory.TAGS:
    options.append(OPTION_OPEN_FOLDER)

    album_path = (ctx.library_root if ctx.library_root else Path(".")) / album.path

    while not done:
        if fixer and fixer.table:
            (headers, rows) = fixer.table
            table = Table(*headers, highlight=False)
            for row in rows:
                table.add_row(*[escape(str(v)) for v in row])
            ctx.console.print(table)

        ctx.console.print(check_result.message, markup=False)

        terminal_menu = TerminalMenu(
            options,
            raise_error_on_interrupt=True,
            title=fixer.prompt if fixer else "select an option",
            cursor_index=fixer.option_automatic_index if fixer and (fixer.option_automatic_index is not None) else do_nothing_index,
        )
        option_index = terminal_menu.show()
        if isinstance(option_index, tuple):
            raise ValueError("unexpected tuple result from TerminalMenu.show")

        if option_index is None or options[option_index] in [OPTION_IGNORE_CHECK, OPTION_DO_NOTHING, OPTION_RUN_TAGGER, OPTION_OPEN_FOLDER]:
            # these options do not invoke fixer.fix
            choice = options[option_index] if option_index else None
            if choice == OPTION_RUN_TAGGER:
                done = False
                ctx.console.print(f"Launching {tagger} {str(album_path)}", markup=False)
                subprocess.Popen([str(tagger), str(album_path)])
                ctx.console.print(f"If you make changes to this album in {tagger} [italic]after[/italic] continuing, scan again later.")
                maybe_changed = True
            elif choice == OPTION_DO_NOTHING:
                done = True
            elif choice == OPTION_IGNORE_CHECK:
                done = prompt_ignore_checks(ctx, album, check_name)
            elif choice == OPTION_OPEN_FOLDER:
                done = False
                os_open_folder(ctx, album_path)
                ctx.console.print("If you make changes to this album [italic]after[/italic] continuing, scan again later.")
            else:  # quit menu without selecting1
                done = Confirm.ask("Do you want to move on to the next album?", default=True, console=ctx.console)

        elif fixer:
            if options[option_index] == OPTION_FREE_TEXT:
                option = ctx.console.input("Enter value: ")
            else:
                option = options[option_index]

            done = Confirm.ask(f'Selected "{option}" - are you sure?', console=ctx.console)
            if done:
                return fixer.fix(option)

            # otherwise loop and ask again

    # TODO if not done + maybe_changed we should probably recheck, and if there are updates, run the same check again
    return maybe_changed


def prompt_ignore_checks(ctx: app.Context, album: Album, check_name: str):
    if not ctx.db:
        raise ValueError("prompt_ignore_checks requires a database connection")
    if album.album_id is None:
        raise ValueError("album does not have an album_id, cannot ignore checks")
    ignore_checks = album.ignore_checks
    if check_name in ignore_checks:
        logger.error(f'did not expect "{check_name}" to already be ignored for {album.path}')
    elif Confirm.ask(f'Do you want to ignore the check "{check_name}" for this album in the future?', console=ctx.console, default=False):
        ignore_checks.append(check_name)
        albums.database.operations.update_ignore_checks(ctx.db, album.album_id, ignore_checks)
        ctx.db.commit()
        return True
    return False


def os_open_folder(ctx: app.Context, path: Path):
    open_folder_command = ctx.config.get("options", {}).get("open_folder_command")
    if not open_folder_command and platform.system() == "Windows":
        # type warnings because startfile only exists on Windows
        # TODO try this on Windows someday
        os.startfile(path)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    elif not open_folder_command and platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen([open_folder_command if open_folder_command else "xdg-open", path])
