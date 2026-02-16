import logging
import sqlite3
from collections.abc import Generator
from typing import Any, Callable

import click
from rich.console import Console

from .config import Configuration
from .types import Album

logger = logging.getLogger(__name__)

SCANNER_VERSION = 1


class Context(dict[Any, Any]):  # this is a dict because it's required to be by click
    console = Console()  # single shared Console
    click_ctx: click.Context | None
    db: sqlite3.Connection | None
    select_albums: Callable[[bool], Generator[Album, None, None]]
    config: Configuration
    filter_collections: list[str]
    filter_paths: list[str]
    filter_regex: bool
    verbose: int = 0

    def is_filtered(self):
        return len(self.filter_collections) > 0 or len(self.filter_paths) > 0

    def __init__(self, *args, **kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        super(Context, self).__init__(*args, **kwargs)
        self.db = None
        self.config = Configuration()
