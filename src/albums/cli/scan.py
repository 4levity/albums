from sqlalchemy.orm import Session

import albums.cli.click_rich as click
from albums.app import Context
from albums.library import run_scan

from .cli_context import pass_context, require_configured, require_library


@click.command(help="scan and update database", add_help_option=False)
@click.option("--reread", "-r", is_flag=True, help="reread tracks even if size/timestamp are unchanged")  # pyright: ignore[reportUnknownMemberType]
@click.help_option("--help", "-h", help="show this message and exit")  # pyright: ignore[reportUnknownMemberType]
@pass_context
def scan(ctx: Context, reread: bool):
    require_configured(ctx)
    require_library(ctx)
    with Session(ctx.db) as session:
        (_, any_changes) = run_scan(ctx, session, ctx.select_album_entities(session) if ctx.is_filtered else None, reread)
        if any_changes:
            session.commit()
