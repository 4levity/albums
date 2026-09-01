from json import dumps

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

import albums.cli.click_rich as click
from albums.app import Context

from .cli_context import pass_context, require_real_context


@click.command(help="run a SQL command against albums db", add_help_option=False)
@click.argument("sql-command", required=True)  # pyright: ignore[reportUnknownMemberType]
@click.option("--json", "-j", is_flag=True, help="output result as JSON object")  # pyright: ignore[reportUnknownMemberType]
@click.help_option("--help", "-h", help="show this message and exit")  # pyright: ignore[reportUnknownMemberType]
@pass_context
def sql(ctx: Context, sql_command: str, json: bool):
    require_real_context(ctx)
    try:
        with ctx.db.begin() as connection:
            cursor = connection.execute(text(sql_command))
            if cursor.returns_rows:
                if json:
                    json_dump = dumps([[v for v in row] for row in cursor.fetchall()])
                    ctx.console.print_json(json_dump)
                else:
                    column_names = list(
                        [
                            str(description[0])
                            for description in (cursor.cursor.description if cursor.cursor and cursor.cursor.description else [("results",)])
                        ]
                    )
                    table = Table(*column_names)
                    for row in cursor:
                        table.add_row(*[escape(str(v) + " ").strip() for v in row])
                    ctx.console.print(table)
            elif json:
                ctx.console.print("[]")
            else:
                ctx.console.print("(no rows returned)")

            connection.commit()
    except OperationalError as err:
        ctx.console.print(Panel(f"[bold]SQL error | [red]{escape(str(err.orig))}", expand=False))
        raise SystemExit(1)
