from json import dumps
from sqlite3 import OperationalError
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
import rich_click as click

from .. import app
from . import cli_context


@click.command(help="run a SQL command against albums db")
@click.argument("sql-command", required=True)
@click.option("--json", "-j", is_flag=True, help="output result as JSON object")
@cli_context.pass_context
def sql(ctx: app.Context, sql_command: str, json: bool):
    if not ctx.db:
        raise ValueError("sql requires database connection")

    try:
        cursor = ctx.db.execute(sql_command)
        if json:
            ctx.console.print_json(dumps(cursor.fetchall()))
            # more compact: ctx.console.print(dumps(cursor.fetchall()))
        else:
            table = Table(*[description[0] for description in cursor.description])
            for row in cursor:
                table.add_row(*[escape(str(v)) for v in row])
            ctx.console.print(table)
    except OperationalError as err:
        ctx.console.print(Panel(f"[bold]SQL error | [red]{escape(str(err))}", expand=False))
        raise SystemExit(1)
