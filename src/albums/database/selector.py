import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Generator, List, Mapping, Tuple

from sqlalchemy import and_, exists, not_, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session, aliased

from ..tagger.types import BasicTag
from ..types import Album, CollectionEntity, IgnoreCheckEntity, TagV, Track

logger: Final = logging.getLogger(__name__)


class Comparator(StrEnum):
    MATCH_REGEX = "~"
    NEQ = "!="
    LTE = "<="
    LT = "<"
    GTE = ">="
    GT = ">"
    EQ = "="


@dataclass(frozen=True)
class Match:
    value: str
    comparator: Comparator = Comparator.EQ


def load_album_entities(session: Session, filter: Mapping[str, List[Match]] = {}, invert: bool = False) -> Generator[Album, None, None]:
    stmt = select(Album)

    collection_names = filter.get("collection", [])
    if collection_names:
        # TODO: make this consistent, maybe everything should be "and" instead of some being "or"
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

    tags: list[Tuple[str, List[Match]]] = [(k.partition(":")[2], matches) for k, matches in filter.items() if k.startswith("tag:")]
    if tags:
        track_match = select(Track.track_id).where(Album.album_id == Track.album_id)
        for tag, matches in tags:
            entity = aliased(TagV)
            clauses = [or_(*(_compare(entity.value, m.comparator, m.value) for m in matches))] if matches else []  # empty = tag exists, any value
            track_match = track_match.join(entity, and_(Track.track_id == entity.track_id, entity.tag == BasicTag(tag), *clauses))
        stmt = stmt.where(not_(exists(track_match))) if invert else stmt.where(exists(track_match))

    yield from (album[0] for album in session.execute(stmt.order_by(Album.path)))


def _compare(value: InstrumentedAttribute[str], comparator: Comparator, target: str):
    match comparator:
        case Comparator.EQ:
            return value == target
        case Comparator.NEQ:
            return value != target
        case Comparator.MATCH_REGEX:
            return value.regexp_match(target)
        case Comparator.LT:
            return value < target
        case Comparator.LTE:
            return value <= target
        case Comparator.GT:
            return value > target
        case Comparator.GTE:
            return value >= target
