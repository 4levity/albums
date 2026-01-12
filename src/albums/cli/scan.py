import click
import logging
from .. import library


logger = logging.getLogger(__name__)


@click.command(help="scan and update database")
@click.pass_context
def scan(ctx: click.Context):
    if ctx.obj.get("SCAN_DONE", False):
        logger.info("scan already done, not scanning again")
        return

    library.scan(ctx.obj["DB_CONNECTION"], ctx.obj["LIBRARY_ROOT"])
