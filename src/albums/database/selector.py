import logging
import re
from typing import Generator, Sequence, TypedDict, Unpack

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from ..types import Album
from .models import AlbumEntity, CollectionEntity
from .operations import album_to_album

logger = logging.getLogger(__name__)


class LoadOptions(TypedDict, total=False):
    load_track_tags: bool
    regex: bool

    collection: Sequence[str]
    path: Sequence[str]


def load_albums(db: Engine, **kwargs: Unpack[LoadOptions]) -> Generator[Album, None, None]:
    def path_match_when_regex(path: str):
        if len(match_paths) == 0 or not match_path_regex:
            return True
        for pattern in match_paths:
            if re.search(pattern, path):
                return True
        return False

    load_track_tags = kwargs.get("load_track_tags", True)
    collection_names = kwargs.get("collection", [])
    match_path_regex = kwargs.get("regex", False)
    match_paths = kwargs.get("path", [])
    with Session(db) as session:
        stmt = select(AlbumEntity)
        if collection_names:
            stmt = stmt.where(AlbumEntity.collections.any(CollectionEntity.collection_name.in_(collection_names)))
        if match_paths and not match_path_regex:
            stmt = stmt.where(AlbumEntity.path.in_(match_paths))

        yield from (
            album_to_album(album[0], load_track_tags)
            for album in session.execute(stmt.order_by(AlbumEntity.path))
            if path_match_when_regex(album[0].path)
        )
