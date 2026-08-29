import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Generator, List, Mapping, Sequence, Tuple

from sqlalchemy import ScalarSelect, and_, exists, not_, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session, aliased

from albums.entities import Album, AlbumCollectionAssociation, CollectionEntity, FieldV, IgnoreCheckEntity, Track
from albums.tagger import BasicField

logger: Final = logging.getLogger(__name__)


class Comparator(StrEnum):
    """Comparison operators for database queries."""

    MATCH_REGEX = "~"
    NEQ = "!="
    LTE = "<="
    LT = "<"
    GTE = ">="
    GT = ">"
    EQ = "="


@dataclass(frozen=True)
class Match:
    """A filter value paired with a comparison operator."""

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
    """Load albums matching the given filters.

    Filters support keys like ``path``, ``collection``, ``ignore_check``, track columns (``bitrate``, ``codec``, etc.), and ``field:artist``.

    Args:
        session: Database session.
        filter: Mapping of filter keys to list of match criteria.
        invert: If true, return albums that don't match any filter.
    """
    stmt = select(Album)
    fields: list[Tuple[str, List[Match]]] = [(k.partition(":")[2], matches) for k, matches in filter.items() if k.startswith("field:")]
    if fields:
        track_match = select(Track.track_id).where(Album.album_id == Track.album_id)
        for field_name, matches in fields:
            entity = aliased(FieldV)
            clauses = [or_(*(_compare(entity.value, m.comparator, m.value) for m in matches))] if matches else []  # empty = field exists, any value
            track_match = track_match.join(entity, and_(Track.track_id == entity.track_id, entity.field == BasicField(field_name), *clauses))
        stmt = stmt.where(not_(exists(track_match))) if invert else stmt.where(exists(track_match))

    for key, matches in ((k, v) for k, v in filter.items() if not k.startswith("field:")):
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
            clause = (
                select(1)
                .where(
                    and_(
                        IgnoreCheckEntity.album_id == Album.album_id,
                        or_(*(_compare(IgnoreCheckEntity.check_name, m.comparator, m.value) for m in matches)),
                    )
                )
                .exists()
            )
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


# It shouldn't be (and isn't strictly) necessary to look up collections or explicitly create them. But the association_proxy creator implementation
# in Album creates a duplicate CollectionEntity if the collection already exists, causing the following warning even though the operation succeeds:
# SAWarning: Identity map already had an identity for (<class 'albums.entities.CollectionEntity'>, (1,), None), replacing it with newly flushed object.
#     Are there load operations occurring inside of an event handler within the flush?
def collections_by_name(session: Session, collection_names: Sequence[str]):
    """Look up existing collections or create new ones by name, returning a name-to-entity mapping."""
    return dict(
        (
            name,
            (
                session.execute(select(CollectionEntity).where(CollectionEntity.collection_name == name)).tuples().one_or_none()
                or (CollectionEntity(collection_name=name),)
            )[0],
        )
        for name in collection_names
    )
