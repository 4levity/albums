from collections.abc import Generator
import logging
from pathlib import Path
from typing import Any, Callable
import click
from rich.console import Console
import sqlite3

from .types import Album


logger = logging.getLogger(__name__)


class Context(dict[Any, Any]):
    console = Console()  # single shared Console
    click_ctx: click.Context | None
    db: sqlite3.Connection | None
    select_albums: Callable[[bool], Generator[Album, None, None]]
    config: dict[str, dict[str, Any]]
    library_root: Path | None
    filter_collections: list[str]
    filter_paths: list[str]
    filter_regex: bool
    rescan_auto: bool = False
    verbose: int = 0

    def is_filtered(self):
        return len(self.filter_collections) > 0 or len(self.filter_paths) > 0

    def __init__(self, *args, **kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        super(Context, self).__init__(*args, **kwargs)
        self.db = None
        self.config = {}
        self.library_root = None
