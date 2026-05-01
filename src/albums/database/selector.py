import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Final, Generator, List, TypedDict, Unpack

from sqlalchemy import and_, exists, not_, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session, aliased

from ..tagger.types import BasicTag
from ..types import Album, CollectionEntity, IgnoreCheckEntity, TagV, Track

logger: Final = logging.getLogger(__name__)


class Comparator(Enum):
    MATCH_REGEX = auto()
    EQ = auto()
    LT = auto()
    GT = auto()


@dataclass(frozen=True)
class Match:
    value: str
    comparator: Comparator = Comparator.EQ


class Filter(TypedDict, total=False):
    regex: bool  # only for tags, TODO remove
    invert: bool
    collection: List[Match]
    path: List[Match]
    ignore_check: List[Match]
    tag: List[Match]


class LoadOptions(Filter, total=False):
    load_track_tags: bool


def load_album_entities(session: Session, **filter: Unpack[Filter]) -> Generator[Album, None, None]:
    invert = filter.get("invert", False)
    regex = filter.get("regex", False)
    stmt = select(Album)

    collection_names = filter.get("collection", [])
    if collection_names:
        # TODO: make this consistent, probably everything should be "and" instead of some being "or"
        clause = or_(
            *(Album.collection_associations.any(_compare(CollectionEntity.collection_name, c.comparator, c.value)) for c in collection_names)
        )
        stmt = stmt.where(not_(clause)) if invert else stmt.where(clause)

    ignore_check_names = filter.get("ignore_check", [])
    if ignore_check_names:
        clause = or_(*(Album.ignore_check_entities.any(_compare(IgnoreCheckEntity.check_name, c.comparator, c.value)) for c in ignore_check_names))
        stmt = stmt.where(not_(clause)) if invert else stmt.where(clause)

    match_paths = filter.get("path", [])
    if match_paths:
        clause = or_(*(_compare(Album.path, c.comparator, c.value) for c in match_paths))
        stmt = stmt.where(not_(clause)) if invert else stmt.where(clause)

    tags = filter.get("tag", [])
    if tags:
        track_match = select(Track.track_id).where(Album.album_id == Track.album_id)
        for spec in tags:
            entity = aliased(TagV)
            kv = spec.value.split(":", 1)
            tag = BasicTag(kv[0])
            if len(kv) == 1:  # tag only, match any value
                track_match = track_match.join(entity, and_(Track.track_id == entity.track_id, entity.tag == tag))
            else:
                value = kv[1]
                if regex:
                    track_match = track_match.join(
                        entity, and_(Track.track_id == entity.track_id, entity.tag == tag, entity.value.regexp_match(value))
                    )
                else:
                    track_match = track_match.join(entity, and_(Track.track_id == entity.track_id, entity.tag == tag, entity.value == value))
        stmt = stmt.where(not_(exists(track_match))) if invert else stmt.where(exists(track_match))

    yield from (album[0] for album in session.execute(stmt.order_by(Album.path)))


def _compare(value: InstrumentedAttribute[str], comparator: Comparator, target: str):
    match comparator:
        case Comparator.EQ:
            return value == target
        case Comparator.MATCH_REGEX:
            return value.regexp_match(target)
        case Comparator.LT:
            return value < target
        case Comparator.GT:
            return value > target
