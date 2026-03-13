import logging
from collections.abc import Generator
from typing import Any, Callable, Self

import click
from rich.console import Console
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from .configuration import Configuration
from .types import Album

logger = logging.getLogger(__name__)

SCANNER_VERSION = 1


class Context(dict[Any, Any]):  # this is a dict because it's required to be by click
    parent: Self | None = None
    console = Console()  # single shared Console
    click_ctx: click.Context | None
    db: Engine
    select_album_entities: Callable[[Session], Generator[Album, None, None]]
    is_filtered: bool
    config: Configuration
    verbose: int = 0
    is_persistent = True

    def __init__(self, *args, **kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        super(Context, self).__init__(*args, **kwargs)
        self.config = Configuration()
