import logging
from pathlib import Path
from typing import Any, Callable, Final, Iterator, Self

import click
from rich.console import Console
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from .config import Configuration
from .types import Album

logger: Final = logging.getLogger(__name__)

SCANNER_VERSION: Final = 7


class Context(dict[Any, Any]):  # this is a dict because it's required to be by click
    parent: Self | None = None
    console = Console()  # single shared Console
    click_ctx: click.Context | None
    db: Engine
    db_path: Path
    select_album_entities: Callable[[Session], Iterator[Album]]
    is_filtered: bool
    config: Configuration
    verbose: int = 0
    is_persistent = True
    prescanned = False
    importing = False

    def __init__(self, *args, **kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        super(Context, self).__init__(*args, **kwargs)
        self.config = Configuration()
