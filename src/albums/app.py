import logging
from collections.abc import Generator
from typing import Any, Callable, Self

import click
from rich.console import Console
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from .configuration import Configuration
from .database.models import AlbumEntity
from .database.operations import album_to_album
from .types import Album

logger = logging.getLogger(__name__)

SCANNER_VERSION = 1


class Context(dict[Any, Any]):  # this is a dict because it's required to be by click
    parent: Self | None = None
    console = Console()  # single shared Console
    click_ctx: click.Context | None
    db: Engine
    select_album_entities: Callable[[Session], Generator[AlbumEntity, None, None]]
    is_filtered: bool
    config: Configuration
    verbose: int = 0
    is_persistent = True

    def select_albums(self, load_track_tags: bool) -> Generator[Album, None, None]:
        with Session(self.db) as session:
            yield from (album_to_album(album, load_track_tags) for album in self.select_album_entities(session))

    def __init__(self, *args, **kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        super(Context, self).__init__(*args, **kwargs)
        self.config = Configuration()
