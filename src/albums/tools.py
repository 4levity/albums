import datetime
import logging
import os
from platformdirs import PlatformDirs


platform_dirs = PlatformDirs("albums", "4levity")


def progress_bar(iterable, get_prefix=lambda: ""):
    item_count = len(iterable)

    def show(iteration):
        prefix = get_prefix()
        try:
            width = max(10, os.get_terminal_size().columns - 8 - len(prefix))
        except OSError:
            width = 80
        fill = int(width * iteration // item_count) if item_count > 0 else width
        percent = ("{0:.0f}").format(100 * (iteration / float(item_count))) if item_count > 0 else "100"
        print(f"\r{prefix}[{'#' * fill + '.' * (width - fill)}] {percent}%", end="\r")

    show(0)
    for i, item in enumerate(iterable):
        yield item
        show(i + 1)

    print()


def format_file_timestamp(timestamp: float):
    return datetime.datetime.fromtimestamp(timestamp).isoformat(sep=" ", timespec="seconds")


def setup_logging(verbose: int):
    log_format = "%(message)s"
    if verbose >= 2:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    elif verbose == 1:
        logging.basicConfig(level=logging.INFO, format=log_format)
    else:
        logging.basicConfig(level=logging.WARNING, format=log_format)
