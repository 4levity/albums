from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from albums.types import CollectionEntity


# It shouldn't be (and isn't strictly) necessary to look up collections or explicitly create them. But the association_proxy creator implementation
# in Album creates a duplicate CollectionEntity if the collection already exists, causing the following warning even though the operation succeeds:
# SAWarning: Identity map already had an identity for (<class 'albums.types.CollectionEntity'>, (1,), None), replacing it with newly flushed object.
#     Are there load operations occurring inside of an event handler within the flush?
def collections_by_name(session: Session, collection_names: Sequence[str]):
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
