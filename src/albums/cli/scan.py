import logging

import rich_click as click
from sqlalchemy.orm import Session

from ..app import Context
from ..config import RescanOption
from ..library import scanner
from .cli_context import pass_context, require_library

logger = logging.getLogger(__name__)


@click.command(help="scan and update database")
@click.option("--reread", "-r", is_flag=True, help="reread tracks even if size/timestamp are unchanged")
@pass_context
def scan(ctx: Context, reread: bool):
    require_library(ctx)
    if ctx.config.rescan == RescanOption.ALWAYS:
        ctx.console.print("scan already done, not scanning again")
        return

    with Session(ctx.db) as session:
        (_, any_changes) = scanner.scan(ctx, session, ctx.select_album_entities(session) if ctx.is_filtered else None, reread)
        if any_changes:
            session.commit()
