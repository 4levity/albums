from dataclasses import dataclass, field
import logging
from pathlib import Path
import subprocess
from rich.markup import escape
from rich.prompt import Confirm
from rich.table import Table
from simple_term_menu import TerminalMenu

import albums.database.operations
from .. import app
from ..types import Album


logger = logging.getLogger(__name__)


@dataclass
class FixerInteractivePrompt:
    message: str | list[str]
    question: str = "Select an option"
    options: list[str] = field(default_factory=list[str])
    show_table: tuple[list[str], list[list[str]]] | None = None  # tuple (headers, row data)
    option_none: bool = False
    option_free_text: bool = False


@dataclass
class Fixer:
    check_name: str
    ctx: app.Context
    album: Album
    has_interactive: bool = False
    describe_automatic: str | None = None
    enable_tagger: bool = False

    ### subclass overrides to define behavior

    def get_interactive_prompt(self) -> FixerInteractivePrompt:
        raise NotImplementedError

    def fix_interactive(self, option: str | None) -> bool:
        raise NotImplementedError

    def fix_automatic(self) -> bool:
        raise NotImplementedError

    ### base functionality

    def interact(self):
        if not self.has_interactive:
            return prompt_ignore_checks(self.ctx, self.album, self.check_name)
        albums_root = self.ctx.library_root if self.ctx.library_root else Path(".")

        prompt = self.get_interactive_prompt()
        done = False  # allow user to start over if canceled by accident or not confirmed
        maybe_changed = False
        while not done:
            if prompt.show_table:
                (headers, rows) = prompt.show_table
                table = Table(*headers, highlight=False)
                for row in rows:
                    table.add_row(*[escape(str(v)) for v in row])
                self.ctx.console.print(table)

            for line in prompt.message if isinstance(prompt.message, list) else [prompt.message]:
                self.ctx.console.print(line, markup=False)

            tagger_config = self.ctx.config.get("options", {}).get("tagger")
            tagger = str(tagger_config) if tagger_config else None
            OPTION_NONE = ">> None / Remove"
            OPTION_FREE_TEXT = ">> Enter Text"
            OPTION_RUN_TAGGER = f">> Edit tags with {tagger}"
            OPTION_DO_NOTHING = ">> Do nothing"  # same as pressing esc
            options = [opt for opt in prompt.options if opt not in [OPTION_NONE, OPTION_FREE_TEXT, OPTION_RUN_TAGGER, OPTION_DO_NOTHING]]
            if prompt.option_none:
                options.append(OPTION_NONE)
            if prompt.option_free_text:
                options.append(OPTION_FREE_TEXT)
            options.append(OPTION_DO_NOTHING)
            if tagger and self.enable_tagger:
                options.append(OPTION_RUN_TAGGER)

            terminal_menu = TerminalMenu(options, raise_error_on_interrupt=True, title=prompt.question)
            option_index = terminal_menu.show()
            if isinstance(option_index, tuple):
                raise ValueError("unexpected tuple result from TerminalMenu.show")
            do_nothing = option_index is None or options[option_index] == OPTION_DO_NOTHING
            run_tagger = option_index is not None and options[option_index] == OPTION_RUN_TAGGER
            if do_nothing or run_tagger:
                if do_nothing:
                    done = prompt_ignore_checks(self.ctx, self.album, self.check_name)
                else:
                    done = False
                    path_str = str(albums_root / self.album.path)
                    self.ctx.console.print(f"Launching {tagger} {path_str}", markup=False)
                    subprocess.Popen([str(tagger), path_str])
                    self.ctx.console.print(f"If you make changes to this album in {tagger} [italic]after[/italic] continuing, scan again later.")
                    maybe_changed = True

                if not done:
                    done = Confirm.ask("Do you want to move on to the next album?", default=True, console=self.ctx.console)
                # TODO if not done and maybe_changed we should probably rescan, and if there are updates, run the check again
            elif option_index is not None:  # option_index definitely isn't None because do_nothing=False here but pyright isn't sure
                if options[option_index] == OPTION_FREE_TEXT:
                    option = self.ctx.console.input("Enter value: ")
                elif options[option_index] == OPTION_NONE:
                    option = None
                else:
                    option = options[option_index]

                done = Confirm.ask(f'Selected "{option}" - are you sure?', console=self.ctx.console)
                if done:
                    return self.fix_interactive(option)

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
