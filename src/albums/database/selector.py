import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Generator, List, Mapping, Tuple

from sqlalchemy import ScalarSelect, and_, exists, not_, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session, aliased

from ..tagger.types import BasicTag
from ..types import Album, AlbumCollectionAssociation, CollectionEntity, IgnoreCheckEntity, TagV, Track

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


_TRACK_COLUMNS: Final = {
    "bitrate": (Track.stream_bitrate, int),
    "bits_per_sample": (Track.stream_bits_per_sample, int),
    "channels": (Track.stream_channels, int),
    "codec": (Track.stream_codec, str),
    "sample_rate": (Track.stream_sample_rate, int),
}


def load_album_entities(session: Session, filter: Mapping[str, List[Match]] = {}, invert: bool = False) -> Generator[Album, None, None]:
    stmt = select(Album)
    tags: list[Tuple[str, List[Match]]] = [(k.partition(":")[2], matches) for k, matches in filter.items() if k.startswith("tag:")]
    if tags:
        track_match = select(Track.track_id).where(Album.album_id == Track.album_id)
        for tag, matches in tags:
            entity = aliased(TagV)
            clauses = [or_(*(_compare(entity.value, m.comparator, m.value) for m in matches))] if matches else []  # empty = tag exists, any value
            track_match = track_match.join(entity, and_(Track.track_id == entity.track_id, entity.tag == BasicTag(tag), *clauses))
        stmt = stmt.where(not_(exists(track_match))) if invert else stmt.where(exists(track_match))

    for key, matches in ((k, v) for k, v in filter.items() if not k.startswith("tag:")):
        if key == "collection":
            # TODO: make this consistent, maybe everything should be "and" instead of some being "or"
            clause = (
                select(AlbumCollectionAssociation)
                .join(CollectionEntity, AlbumCollectionAssociation.collection_id == CollectionEntity.collection_id)
                .where(
                    and_(
                        AlbumCollectionAssociation.album_id == Album.album_id,
                        or_(*(_compare(CollectionEntity.collection_name, m.comparator, m.value) for m in matches)),
                    )
                )
                .exists()
            )
        elif key == "ignore_check":
            clause = or_(*(Album.ignore_check_entities.any(_compare(IgnoreCheckEntity.check_name, m.comparator, m.value)) for m in matches))
        elif key == "path":
            clause = or_(*(_compare(Album.path, m.comparator, m.value) for m in matches))
        elif key in _TRACK_COLUMNS:
            (column, cls) = _TRACK_COLUMNS[key]
            track_matchers = (_compare(column, m.comparator, cls(m.value)) for m in matches)
            clause = exists(Track.track_id).where(and_(Track.album_id == Album.album_id, *track_matchers))
        else:
            raise ValueError(f"invalid filter key {key}")
        stmt = stmt.where(not_(clause)) if invert else stmt.where(clause)

    yield from (album[0] for album in session.execute(stmt.order_by(Album.path)))


def _compare(
    value: InstrumentedAttribute[str] | InstrumentedAttribute[int] | ScalarSelect[str] | ScalarSelect[int], comparator: Comparator, target: str | int
):
    match comparator:
        case Comparator.EQ:
            return value == target
        case Comparator.NEQ:
            return value != target
        case Comparator.MATCH_REGEX:
            return value.regexp_match(str(target))
        case Comparator.LT:
            return value < target
        case Comparator.LTE:
            return value <= target
        case Comparator.GT:
            return value > target
        case Comparator.GTE:
            return value >= target
