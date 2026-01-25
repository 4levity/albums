import logging
from pathlib import Path
from typing import Any
from rich.console import Console
import sqlite3

import albums.database.selector


logger = logging.getLogger(__name__)


class Context(dict[Any, Any]):
    console = Console()  # single shared Console
    db: sqlite3.Connection | None
    config: dict[str, dict[str, Any]]
    library_root: Path | None
    filter_collections: list[str]
    filter_paths: list[str]
    filter_regex: bool

    def is_filtered(self):
        return len(self.filter_collections) > 0 or len(self.filter_paths) > 0

    def select_albums(self, load_track_tag: bool):
        if not self.db:
            raise ValueError("select_albums called with no db connection")
        return albums.database.selector.select_albums(self.db, self.filter_collections, self.filter_paths, self.filter_regex, load_track_tag)

    def __init__(self, *args, **kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        super(Context, self).__init__(*args, **kwargs)
        self.db = None
        self.config = {}
        self.library_root = None
