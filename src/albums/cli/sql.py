from json import dumps
from rich.markup import escape
from rich.table import Table
import rich_click as click

from .. import app
from . import cli_context


@click.command(help="run a SQL command against albums db")
@click.argument("sql-command", required=True)
@click.option("--json", "-j", is_flag=True, help="output result as JSON object")
@cli_context.pass_context
def sql(ctx: app.Context, sql_command, json):
    rows = list(ctx.db.execute(sql_command).fetchall())
    if json:
        ctx.console.print_json(dumps(rows))
    else:
        table = Table(show_header=False, highlight=False)
        for row in rows:
            table.add_row(*[escape(str(v)) for v in row])
        ctx.console.print(table)
