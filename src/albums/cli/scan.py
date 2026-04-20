import logging
from typing import Final

import rich_click as click
from sqlalchemy.orm import Session

from ..app import Context
from ..library import scanner
from .cli_context import pass_context, require_configured, require_library

logger: Final = logging.getLogger(__name__)


@click.command(help="scan and update database", add_help_option=False)
@click.option("--reread", "-r", is_flag=True, help="reread tracks even if size/timestamp are unchanged")
@click.help_option("--help", "-h", help="show this message and exit")
@pass_context
def scan(ctx: Context, reread: bool):
    require_configured(ctx)
    require_library(ctx)
    if ctx.prescanned:
        logger.debug("scan already done, not scanning again")
        return
    with Session(ctx.db) as session:
        (_, any_changes) = scanner.scan(ctx, session, ctx.select_album_entities(session) if ctx.is_filtered else None, reread)
        if any_changes:
            session.commit()
