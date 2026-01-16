import click
from dataclasses import dataclass
import logging
from prettytable import PrettyTable
from simple_term_menu import TerminalMenu


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
    has_interactive: bool = False
    has_automatic: bool = False

    ### subclass overrides to define behavior

    def get_interactive_prompt(self) -> FixerInteractivePrompt | None:
        return None

    def fix_interactive(self, option: str | None) -> bool:
        return False

    def automatic(self) -> bool:
        return False

    ### base functionality

    def interact(self):
        prompt = self.get_interactive_prompt() if self.has_interactive else None
        if not prompt:
            logger.warning(f"interact() was called but no prompt available {self.__class__.__name__}")
            return False

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
            terminal_menu = TerminalMenu(
                options,
                raise_error_on_interrupt=True,
                title=prompt.question,
            )
            option_index = terminal_menu.show()
            if option_index is None:
                done = click.confirm("selection canceled, do you want to move on?", default=True)
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
