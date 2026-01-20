import logging
from pathlib import Path
from rich.console import Console
import sqlite3

import albums.database.selector


logger = logging.getLogger(__name__)


class Context(dict):  # click requires this object to be a dict
    console = Console()  # single shared Console
    db: sqlite3.Connection | None
    config: dict
    library_root: Path | None
    _collections: list[str]
    _paths: list[str]
    _regex: bool

    def is_filtered(self):
        return len(self._collections) > 0 or len(self._paths) > 0

    def select_albums(self, load_track_tag: bool):
        return albums.database.selector.select_albums(self.db, self._collections, self._paths, self._regex, load_track_tag)

    def __init__(self, *args, **kwargs):
        super(Context, self).__init__(*args, **kwargs)
        self.db = None
        self.config = {}
        self.library_root = None
