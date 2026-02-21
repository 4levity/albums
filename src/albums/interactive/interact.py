import logging
import os
import platform
import subprocess
from pathlib import Path

from prompt_toolkit.shortcuts import choice
from rich.markup import escape
from rich.prompt import Confirm
from rich.table import Table

from ..app import Context
from ..database import operations
from ..types import Album, CheckResult, ProblemCategory

logger = logging.getLogger(__name__)

OPTION_FREE_TEXT = ">> Enter Text"
OPTION_OPEN_FOLDER = ">> Open folder and see all files"
OPTION_DO_NOTHING = ">> Do nothing"
OPTION_IGNORE_CHECK = ">> Ignore this check for this album"


def interact(ctx: Context, check_name: str, check_result: CheckResult, album: Album) -> tuple[bool, bool]:
    # if there is a fixer, offer the options it provides
    # always offer these options:
    #  - do nothing
    #  - ignore this check for this album
    #  - run tagger (if configured + issue is tag related)
    #  - open new window to browse album folder
    # if there is an automatic fix option, it is the default, otherwise do nothing is the default

    fixer = check_result.fixer
    done = False  # allow user to start over if canceled by accident or not confirmed
    maybe_changed = False
    user_quit = False  # user explicitly quit this checkRenderableType

    tagger_config = ctx.config.tagger
    # TODO should we just always show tagger?
    tagger = tagger_config if check_result.category in {ProblemCategory.TAGS, ProblemCategory.FILENAMES, ProblemCategory.PICTURES} and tagger_config else None

    OPTION_RUN_TAGGER = f">> Edit tags with {tagger}"

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
    options.append(OPTION_OPEN_FOLDER)

    album_path = ctx.config.library / album.path

    while not done:
        table = fixer.get_table() if fixer else None
        if table:
            (headers, rows) = table
            table = Table(*headers)
            for row in rows:
                table.add_row(*row)
            ctx.console.print(table)

        ctx.console.print(f"[bold]{check_name}[/bold]: {escape(check_result.message)}")

        prompt_text = fixer.prompt if fixer else "select an option"
        default_option_index = fixer.option_automatic_index if fixer and (fixer.option_automatic_index is not None) else do_nothing_index
        option_index = choose_from_menu(ctx, prompt_text, options, default_option_index)

        if option_index is None or options[option_index] in [OPTION_IGNORE_CHECK, OPTION_DO_NOTHING, OPTION_RUN_TAGGER, OPTION_OPEN_FOLDER]:
            # these options do not use the fixer (if one was provided)
            choice = options[option_index] if option_index is not None else None
            if choice == OPTION_RUN_TAGGER:
                ctx.console.print(f"Launching {tagger} {str(album_path)}", markup=False)
                subprocess.Popen([str(tagger), str(album_path)])
                while not Confirm.ask("Done making changes in external program?", console=ctx.console):
                    pass
                maybe_changed |= True
                done = True
            elif choice == OPTION_DO_NOTHING:
                done = True
                user_quit = True
            elif choice == OPTION_IGNORE_CHECK:
                done = prompt_ignore_checks(ctx, album, check_name)
                user_quit = done
            elif choice == OPTION_OPEN_FOLDER:
                ctx.console.print(f"Opening folder {str(album_path)}", markup=False)
                os_open_folder(ctx, album_path)
                ctx.console.print()
                while not Confirm.ask("Done making changes in external program?", console=ctx.console):
                    pass
                maybe_changed |= True
                done = True
            elif choice is None:  # if user pressed esc, confirm
                done = Confirm.ask("Do you want to move on to the next check?", default=True, console=ctx.console)
                user_quit = done

        elif fixer:
            if options[option_index] == OPTION_FREE_TEXT:
                option = ctx.console.input("Enter value: ")
            else:
                option = options[option_index]

            maybe_changed |= fixer.fix(option)
            done = maybe_changed  # if that fixer option didn't change anything, loop

        # otherwise loop and ask again

    return (maybe_changed, user_quit)


def prompt_ignore_checks(ctx: Context, album: Album, check_name: str):
    if not ctx.db:
        raise ValueError("prompt_ignore_checks requires a database connection")
    if album.album_id is None:
        raise ValueError("album does not have an album_id, cannot ignore checks")
    ignore_checks = album.ignore_checks
    if check_name in ignore_checks:
        logger.error(f'did not expect "{check_name}" to already be ignored for {album.path}')
    elif Confirm.ask(f'Do you want to ignore the check "{check_name}" for this album in the future?', console=ctx.console, default=False):
        ignore_checks.append(check_name)
        operations.update_ignore_checks(ctx.db, album.album_id, ignore_checks)
        return True
    return False


def os_open_folder(ctx: Context, path: Path):
    open_folder_command = ctx.config.open_folder_command
    if not open_folder_command and platform.system() == "Windows":
        # type warnings because startfile only exists on Windows
        os.startfile(path)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    elif not open_folder_command and platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen([open_folder_command if open_folder_command else "xdg-open", path])


def choose_from_menu(ctx: Context, prompt: str, options: list[str], default_option_index: int | None) -> int | None:
    default_option = options[default_option_index] if default_option_index is not None else None
    selection = choice(message=prompt, options=[(o, o) for o in options], default=default_option)
    return options.index(selection)
