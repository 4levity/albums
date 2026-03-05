from json import dumps

import rich_click as click
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from ..app import Context
from .cli_context import pass_context


@click.command(help="run a SQL command against albums db")
@click.argument("sql-command", required=True)
@click.option("--json", "-j", is_flag=True, help="output result as JSON object")
@pass_context
def sql(ctx: Context, sql_command: str, json: bool):
    try:
        with ctx.db.begin() as connection:
            cursor = connection.execute(text(sql_command))
            if json:
                json_dump = dumps([[v for v in row] for row in cursor.fetchall()])
                ctx.console.print_json(json_dump)
                # ctx.console.print_json(dumps([row[0] for row in cursor.fetchall()]))
                # more compact: ctx.console.print(dumps(cursor.fetchall()))
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
            connection.commit()
    except OperationalError as err:
        ctx.console.print(Panel(f"[bold]SQL error | [red]{escape(str(err.orig))}", expand=False))
        raise SystemExit(1)
