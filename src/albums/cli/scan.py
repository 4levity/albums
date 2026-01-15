import click
import logging
from ..library import scanner


logger = logging.getLogger(__name__)


@click.command(help="scan and update database")
@click.option("--reread", "-r", is_flag=True, help="reread tracks even if size/timestamp are unchanged")
@click.pass_context
def scan(ctx: click.Context, reread: bool):
    if ctx.obj.get("SCAN_DONE", False):
        logger.info("scan already done, not scanning again")
        return

    def filtered_path_selector():
        yield from ((album.path, album.album_id) for album in ctx.obj["SELECT_ALBUMS"](False))

    file_types = ctx.obj["CONFIG"].get("locations", {}).get("supported_file_types", "|".join(scanner.DEFAULT_SUPPORTED_FILE_TYPES)).split("|")
    scanner.scan(ctx.obj["DB_CONNECTION"], ctx.obj["LIBRARY_ROOT"], file_types, filtered_path_selector if ctx.obj["IS_FILTERED"] else None, reread)
