import logging
from typing import Generator, Sequence, TypedDict, Unpack

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, aliased

from ..tagger.types import BasicTag
from ..types import Album, AlbumCollectionAssociation, CollectionEntity, IgnoreCheckEntity, Tag, Track

logger = logging.getLogger(__name__)


class LoadEntityOptions(TypedDict, total=False):
    regex: bool
    collection: Sequence[str]
    path: Sequence[str]
    ignore_check: Sequence[str]
    tag: Sequence[str]


class LoadOptions(LoadEntityOptions, total=False):
    load_track_tags: bool


def load_album_entities(session: Session, **kwargs: Unpack[LoadEntityOptions]) -> Generator[Album, None, None]:
    regex = kwargs.get("regex", False)
    stmt = select(Album)

    collection_names = kwargs.get("collection", [])
    if collection_names and regex:
        stmt = stmt.where(
            Album.collection_associations.any(
                and_(
                    CollectionEntity.collection_id == AlbumCollectionAssociation.collection_id,
                    or_(*(CollectionEntity.collection_name.regexp_match(c) for c in collection_names)),
                )
            )
        )
    elif collection_names:
        stmt = stmt.where(
            Album.collection_associations.any(
                and_(
                    CollectionEntity.collection_id == AlbumCollectionAssociation.collection_id,
                    CollectionEntity.collection_name.in_(collection_names),
                )
            )
        )

    ignore_check_names = kwargs.get("ignore_check", [])
    if ignore_check_names and regex:
        stmt = stmt.where(Album.ignore_check_entities.any(and_(*(IgnoreCheckEntity.check_name.regexp_match(c) for c in ignore_check_names))))
    elif ignore_check_names:
        stmt = stmt.where(Album.ignore_check_entities.any(IgnoreCheckEntity.check_name.in_(ignore_check_names)))

    match_paths = kwargs.get("path", [])
    if match_paths and regex:
        stmt = stmt.where(or_(*(Album.path.regexp_match(path_re) for path_re in match_paths)))
    elif match_paths:
        stmt = stmt.where(Album.path.in_(match_paths))

    tags = kwargs.get("tag", [])
    if tags:
        stmt = stmt.distinct().join(Track, Album.album_id == Track.album_id)
        for spec in tags:
            entity = aliased(Tag)
            kv = spec.split(":", 1)
            tag = BasicTag(kv[0])
            if len(kv) == 1:  # tag only, match any value
                stmt = stmt.join(entity, and_(Track.track_id == entity.track_id, entity.tag == tag))
            else:
                value = kv[1]
                if regex:
                    stmt = stmt.join(entity, and_(Track.track_id == entity.track_id, entity.tag == tag, entity.value.regexp_match(value)))
                else:
                    stmt = stmt.join(entity, and_(Track.track_id == entity.track_id, entity.tag == tag, entity.value == value))
    yield from (album[0] for album in session.execute(stmt.order_by(Album.path)))
