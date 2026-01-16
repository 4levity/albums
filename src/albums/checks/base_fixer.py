import click
from dataclasses import dataclass
import logging
from prettytable import PrettyTable
from simple_term_menu import TerminalMenu

import albums.database.operations
from ..context import AppContext
from ..types import Album


logger = logging.getLogger(__name__)


@dataclass
class FixerInteractivePrompt:
    message: str | list[str]
    question: str
    options: list[str]
    option_none: bool = False
    option_free_text: bool = False
    show_table: tuple[list[str], list[list[str]]] | None = None  # tuple (headers, row data)


@dataclass
class Fixer:
    check_name: str
    ctx: AppContext
    album: Album
    has_interactive: bool = False
    has_automatic: bool = False

    ### subclass overrides to define behavior

    def get_interactive_prompt(self) -> FixerInteractivePrompt:
        raise NotImplementedError

    def fix_interactive(self, option: str | None) -> bool:
        raise NotImplementedError

    def automatic(self) -> bool:
        raise NotImplementedError

    ### base functionality

    def interact(self):
        if not self.has_interactive:
            self._prompt_ignore()
            return False

        prompt = self.get_interactive_prompt()
        done = False  # allow user to start over if canceled by accident or not confirmed
        while not done:
            if prompt.show_table:
                (headers, rows) = prompt.show_table
                table = PrettyTable(headers, align="l")
                table.add_rows(rows)
                click.echo(table.get_string(sortby=headers[0]))

            for line in prompt.message if isinstance(prompt.message, list) else [prompt.message]:
                click.echo(line)

            OPTION_NONE = ">> None / Remove <<"
            OPTION_FREE_TEXT = ">> Enter Text <<"
            options = [opt for opt in prompt.options if opt not in [OPTION_NONE, OPTION_FREE_TEXT]]
            if prompt.option_none or prompt.option_free_text:
                if len(options) > 0:
                    options.append(None)
                if prompt.option_free_text:
                    options.append(OPTION_FREE_TEXT)
                if prompt.option_none:
                    options.append(OPTION_NONE)
            terminal_menu = TerminalMenu(options, raise_error_on_interrupt=True, title=prompt.question)
            option_index = terminal_menu.show()
            if option_index is None:
                done = self._prompt_ignore()
                if not done:
                    done = click.confirm("do you want to move on to the next album?", default=True)
            else:
                if options[option_index] == OPTION_FREE_TEXT:
                    option = click.prompt("Enter value", type=str)
                elif options[option_index] == OPTION_NONE:
                    option = None
                else:
                    option = options[option_index]

                done = click.confirm(f'selected "{option}" - are you sure?')
                if done:
                    return self.fix_interactive(option)

    def _prompt_ignore(self):
        ignore_checks = self.album.ignore_checks
        if self.check_name in ignore_checks:
            logger.error(f'did not expect "{self.check_name}" to already be ignored for {self.album.path}')
        elif click.confirm(f'do you want to ignore the check "{self.check_name}" for this album in the future?'):
            ignore_checks.append(self.check_name)
            albums.database.operations.update_ignore_checks(self.ctx.db, self.album.album_id, ignore_checks)
            self.ctx.db.commit()
            return True

        return False
