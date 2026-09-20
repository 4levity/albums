"""Query the database for albums and collections, including filterable album selection."""

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, Generator, Iterable, List, Mapping, Sequence, Tuple

from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.orm import Session, selectinload

from albums.entities import Album, AlbumCollectionAssociation, CollectionEntity, IgnoreCheckEntity, Track
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
            track_match = track_match.where(_field_values_match(BasicField(field_name), matches))
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


def preload_albums(session: Session, album_ids: Iterable[int | None], batch_size: int = 500) -> None:
    """Eagerly load the track, picture and file relationships of the given albums.

    Checks read ``track.pictures`` and ``track.legacy_fields`` for every track; without this preload
    each access issues its own query (one per track per album). Albums already in the session are
    updated in place (identity map), so this is safe to call after the albums have been selected,
    and again after a commit, which expires the previously loaded relationships.
    None ids (albums not yet persisted) are skipped.
    """
    ids = [album_id for album_id in album_ids if album_id is not None]
    for start in range(0, len(ids), batch_size):
        # the result must be consumed: eager loads are applied while rows are fetched
        session.execute(
            select(Album)
            .where(Album.album_id.in_(ids[start : start + batch_size]))
            .options(
                selectinload(Album.tracks).selectinload(Track.pictures),
                selectinload(Album.tracks).selectinload(Track.legacy_field_entities),
                selectinload(Album.picture_files),
                selectinload(Album.other_files),
                selectinload(Album.ignore_check_entities),
            )
        ).all()


def _field_values_match(field: BasicField, matches: List[Match]):
    """Build an EXISTS clause: some value of *field* on the track's stored fields satisfies the matches (OR'd); no matches = the field is present with any value."""
    values = func.json_each(func.json_extract(Track.fields, f"$.{field.value}")).table_valued("value")
    stmt = select(1).select_from(values)
    if matches:
        stmt = stmt.where(or_(*(_compare(values.c.value, m.comparator, m.value) for m in matches)))
    return stmt.exists()


def _compare(value: Any, comparator: Comparator, target: str | int):
    """Build a SQLAlchemy comparison clause for a column expression (an instrumented attribute, a scalar select or a table-valued column)."""
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
