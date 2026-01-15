import click
import logging

from ..library import scanner
from ..context import AppContext, pass_app_context


logger = logging.getLogger(__name__)


@click.command(help="scan and update database")
@click.option("--reread", "-r", is_flag=True, help="reread tracks even if size/timestamp are unchanged")
@pass_app_context
def scan(ctx: AppContext, reread: bool):
    if str.lower(ctx.config.get("options", {}).get("always_scan", "false")) != "false":
        logger.info("scan already done, not scanning again")
        return

    def filtered_path_selector():
        yield from ((album.path, album.album_id) for album in ctx.select_albums(False))

    file_types = ctx.config.get("locations", {}).get("supported_file_types", "|".join(scanner.DEFAULT_SUPPORTED_FILE_TYPES)).split("|")
    scanner.scan(ctx.db, ctx.library_root, file_types, filtered_path_selector if ctx.is_filtered() else None, reread)
