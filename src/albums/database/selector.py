import logging
from typing import Generator, Sequence, TypedDict, Unpack

from sqlalchemy import Engine, and_, or_, select
from sqlalchemy.orm import Session, aliased

from ..tagger.types import BasicTag
from ..types import Album
from .models import AlbumEntity, CollectionEntity, IgnoreCheckEntity, TrackEntity, TrackTagEntity
from .operations import album_to_album

logger = logging.getLogger(__name__)


class LoadEntityOptions(TypedDict, total=False):
    regex: bool
    collection: Sequence[str]
    path: Sequence[str]
    ignore_check: Sequence[str]
    tag: Sequence[str]


class LoadOptions(LoadEntityOptions, total=False):
    load_track_tags: bool


def load_albums(db: Engine, **kwargs: Unpack[LoadOptions]) -> Generator[Album, None, None]:
    load_track_tags = kwargs.get("load_track_tags", True)
    with Session(db) as session:
        yield from (album_to_album(album, load_track_tags) for album in load_album_entities(session, **kwargs))


def load_album_entities(session: Session, **kwargs: Unpack[LoadEntityOptions]) -> Generator[AlbumEntity, None, None]:
    regex = kwargs.get("regex", False)
    stmt = select(AlbumEntity)

    collection_names = kwargs.get("collection", [])
    if collection_names and regex:
        stmt = stmt.where(AlbumEntity.collections.any(and_(*(CollectionEntity.collection_name.regexp_match(c) for c in collection_names))))
    elif collection_names:
        stmt = stmt.where(AlbumEntity.collections.any(CollectionEntity.collection_name.in_(collection_names)))

    ignore_check_names = kwargs.get("ignore_check", [])
    if ignore_check_names and regex:
        stmt = stmt.where(AlbumEntity.ignore_checks.any(and_(*(IgnoreCheckEntity.check_name.regexp_match(c) for c in ignore_check_names))))
    elif ignore_check_names:
        stmt = stmt.where(AlbumEntity.ignore_checks.any(IgnoreCheckEntity.check_name.in_(ignore_check_names)))

    match_paths = kwargs.get("path", [])
    if match_paths and regex:
        stmt = stmt.where(or_(*(AlbumEntity.path.regexp_match(path_re) for path_re in match_paths)))
    elif match_paths:
        stmt = stmt.where(AlbumEntity.path.in_(match_paths))

    tags = kwargs.get("tag", [])
    if tags:
        stmt = stmt.distinct().join(TrackEntity, AlbumEntity.album_id == TrackEntity.album_id)
        for spec in tags:
            entity = aliased(TrackTagEntity)
            kv = spec.split(":", 1)
            tag = BasicTag(kv[0])
            if len(kv) == 1:  # tag only, match any value
                stmt = stmt.join(entity, and_(TrackEntity.track_id == entity.track_id, entity.tag == tag))
            else:
                value = kv[1]
                if regex:
                    stmt = stmt.join(entity, and_(TrackEntity.track_id == entity.track_id, entity.tag == tag, entity.value.regexp_match(value)))
                else:
                    stmt = stmt.join(entity, and_(TrackEntity.track_id == entity.track_id, entity.tag == tag, entity.value == value))
    yield from (album[0] for album in session.execute(stmt.order_by(AlbumEntity.path)))
