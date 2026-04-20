import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Final, Sequence, Tuple

from prompt_toolkit.shortcuts import choice, confirm
from rich.markup import escape
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..app import Context
from ..types import Album, CheckResult, FixResult

logger: Final = logging.getLogger(__name__)

OPTION_FREE_TEXT: Final = ">> Enter Text"
OPTION_DO_NOTHING: Final = ">> Do nothing"
OPTION_MORE_OPTIONS: Final = ">> More options..."

OPTION_SCAN_AGAIN: Final = ">> Scan again / go back"
OPTION_OPEN_FOLDER: Final = ">> Open folder and see all files"
OPTION_IGNORE_CHECK: Final = ">> Ignore this check for this album"


def interact(
    ctx: Context, session: Session, check_name: str, check_result: CheckResult, album: Album, show_ignore_option: bool
) -> Tuple[bool, bool, bool]:
    fixer = check_result.fixer
    done = False  # allow user to start over if canceled by accident or not confirmed
    maybe_changed = False
    deleted = False
    user_quit = False  # user explicitly quit this checkRenderableType

    OPTION_RUN_TAGGER = f">> Edit tags with {ctx.config.tagger or 'external tagger'}"

    options: list[str] = []
    more_options: list[str] = []

    if fixer:
        # if there is a fixer, offer the options it specifies
        options.extend(fixer.options)
    if fixer and fixer.option_free_text:
        options.append(OPTION_FREE_TEXT)
    if show_ignore_option:
        more_options.append(OPTION_IGNORE_CHECK)
    do_nothing_index = len(options)
    options.append(OPTION_DO_NOTHING)
    if ctx.config.tagger or _in_gui():  # all default taggers require windowing session, don't assume user option does
        more_options.append(OPTION_RUN_TAGGER)
    more_options.append(OPTION_OPEN_FOLDER)  # works without GUI if nnn or mc installed
    more_options.append(OPTION_SCAN_AGAIN)
    options.append(OPTION_MORE_OPTIONS)

    album_path = ctx.config.library / album.path

    while not done:
        table = fixer.get_table() if fixer else None
        if table:
            (headers, rows) = table
            table = Table(*headers)
            for row in rows:
                table.add_row(*row)
            ctx.console.print(table)

        ctx.console.print(f"[bold]{check_name}[/bold]: [bold yellow]{escape(check_result.message)}[/bold yellow]", highlight=False)

        prompt_text = fixer.prompt if fixer else "select an option"
        # if there is an automatic fix option, it is the default, otherwise do nothing is the default
        default_option_index = fixer.option_automatic_index if fixer and (fixer.option_automatic_index is not None) else do_nothing_index
        option_index = _choose_from_menu(prompt_text, options, default_option_index)
        ctx.console.print()

        if option_index is None or options[option_index] in [OPTION_MORE_OPTIONS, OPTION_DO_NOTHING]:
            # these options do not use the fixer (if one was provided)
            selection = options[option_index] if option_index is not None else None
            if selection == OPTION_DO_NOTHING:
                done = True
                user_quit = True
            elif selection == OPTION_MORE_OPTIONS:
                option_index = _choose_from_menu("select an option", more_options, 0)
                selection = more_options[option_index] if option_index is not None else None
                if selection == OPTION_RUN_TAGGER:
                    _run_tagger(ctx, album_path)
                    maybe_changed = True
                    done = True
                elif selection == OPTION_IGNORE_CHECK:
                    done = prompt_ignore_checks(session, album.album_id, check_name) if album.album_id is not None else False
                    maybe_changed |= done
                    user_quit = done
                elif selection == OPTION_OPEN_FOLDER:
                    _open_folder(ctx, album_path)
                    # opening GUI file explorer via OS will return immediately
                    while _in_gui() and not confirm("Done making changes in external program?"):
                        pass
                    maybe_changed = True
                    done = True
                elif selection == OPTION_SCAN_AGAIN:
                    maybe_changed = True
                    done = True
                ctx.console.print()
            elif selection is None:  # if user pressed esc, confirm
                done = confirm("Do you want to move on to the next check?")
                user_quit = done

        elif fixer:
            if options[option_index] == OPTION_FREE_TEXT:
                option = ctx.console.input("Enter value: ")
            else:
                option = options[option_index]

            fix_result = fixer.fix(option)
            maybe_changed |= fix_result != FixResult.NO_CHANGE
            deleted |= fix_result == FixResult.DELETED_ALBUM
            done = maybe_changed  # if that fixer option didn't change anything, loop

        if maybe_changed:
            session.flush()
        # otherwise loop and ask again

    return (maybe_changed, deleted, user_quit)


def prompt_ignore_checks(session: Session, album_id: int, check_name: str):
    album = session.execute(select(Album).where(Album.album_id == album_id)).tuples().one()[0]
    if check_name in album.ignore_checks:
        logger.error(f'did not expect "{check_name}" to already be ignored for {album.path}')
        return True

    if confirm(f'Do you want to ignore the check "{check_name}" for this album?'):
        album.ignore_checks.append(check_name)
        session.commit()
        return True

    return False


def _open_folder(ctx: Context, path: Path):
    ctx.console.print(f"Opening folder {str(path)}", markup=False)
    if ctx.config.open_folder_command:
        _try_to_run(ctx, [ctx.config.open_folder_command], [str(path)], "settings.open_folder_command")
    else:
        if platform.system() == "Windows":
            if _in_gui():
                # type warnings because startfile only exists on Windows
                os.startfile(path)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            else:
                raise RuntimeError("not in GUI, can't launch file manager")  # not possible while we assume GUI on Windows
        else:
            if _in_gui():
                try_commands = ["open"] if platform.system() == "Darwin" else ["xdg-open", "open"]
            else:
                try_commands = ["nnn", "mc"]
            _try_to_run(ctx, try_commands, [str(path)], "settings.open_folder_command")
    ctx.console.print()


def _run_tagger(ctx: Context, album_path: Path):
    if ctx.config.tagger:
        _try_to_run(ctx, [ctx.config.tagger], [str(album_path)], "settings.tagger")
    else:
        if _in_gui():
            _try_to_run(ctx, ["easytag", "puddletag", "mp3tag"], [str(album_path)], "settings.tagger")
        else:
            raise RuntimeError("can't launch tagger, don't seem to be in GUI")  # tagger option shouldn't be shown if not GUI


def _in_gui() -> bool:
    return "DISPLAY" in os.environ or platform.system() == "Windows"  # TODO fancier GUI detection, don't assume GUI on Windows


def _try_to_run(ctx: Context, commands: Sequence[str], params: Sequence[str], setting_name: str):
    command = next((cmd for cmd in commands if shutil.which(cmd)), None)
    if command:
        ctx.console.print(f"Running {command} {escape(' '.join(f'"{param}"' for param in params))}", highlight=False)
        subprocess.run([command, *params])
        ctx.console.print()
    else:
        ctx.console.print(f"Could not find command {' or '.join(f'"{cmd}"' for cmd in commands)} - see configuration option {setting_name}")


def _choose_from_menu(prompt: str, options: list[str], default_option_index: int | None) -> int | None:
    default_option = options[default_option_index] if default_option_index is not None else None
    selection = choice(message=prompt, options=[(o, o) for o in options], default=default_option)
    return options.index(selection)
