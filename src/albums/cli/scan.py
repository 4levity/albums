from sqlalchemy.orm import Session

import albums.cli.click_rich as click
from albums.app import Context, require_configured, require_library
from albums.library import run_scan

from .cli_context import pass_context


@click.command(help="scan and update database", add_help_option=False)
@click.option("--reread", "-r", is_flag=True, help="reread tracks even if size/timestamp are unchanged")  # pyright: ignore[reportUnknownMemberType]
@click.help_option("--help", "-h", help="show this message and exit")  # pyright: ignore[reportUnknownMemberType]
@pass_context
def scan(ctx: Context, reread: bool):
    require_configured(ctx)
    require_library(ctx)
    with Session(ctx.db) as session:
        selector = ctx.album_selector()
        (_, any_changes) = run_scan(ctx, session, selector.albums(session) if selector.is_filtered() else None, reread)
        if any_changes:
            session.commit()
