import re
import sqlite3
from typing import Generator, Sequence, TypedDict, Unpack

from ..types import Album
from . import operations


class LoadOptions(TypedDict, total=False):
    load_track_tags: bool
    collection_names: Sequence[str]
    match_paths: Sequence[str]
    match_path_regex: bool


def load_albums(db: sqlite3.Connection, **kwargs: Unpack[LoadOptions]) -> Generator[Album, None, None]:
    load_track_tags = kwargs.get("load_track_tags", True)
    collection_names = kwargs.get("collection_names", [])
    match_path_regex = kwargs.get("match_path_regex", False)
    match_paths = kwargs.get("match_paths", [])
    collection_placeholders = ",".join(["?"] * len(collection_names))
    if len(match_paths) == 0 or match_path_regex:  # no path filter
        if len(collection_names) == 0:
            cursor = db.execute("SELECT album_id, path FROM album ORDER BY path;")
        else:
            cursor = db.execute(
                "SELECT album_id, path FROM album "
                "WHERE album_id IN "
                "(SELECT album_id FROM album_collection ac JOIN collection c ON ac.collection_id=c.collection_id "
                f"WHERE collection_name IN ({collection_placeholders})) "
                "ORDER BY path;",
                collection_names,
            )
    else:  # with path filter
        path_placeholders = ",".join(["?"] * len(match_paths))
        if len(collection_names) == 0:
            cursor = db.execute(f"SELECT album_id, path FROM album WHERE path IN ({path_placeholders}) ORDER BY path;", match_paths)
        else:
            cursor = db.execute(
                "SELECT album_id, path FROM album "
                f"WHERE path IN ({path_placeholders}) AND album_id IN "
                "(SELECT album_id FROM album_collection ac JOIN collection c ON ac.collection_id=c.collection_id "
                f"WHERE collection_name IN {collection_placeholders}) "
                "ORDER BY path;",
                (*match_paths, *collection_names),
            )

    def path_match_when_regex(path: str):
        if len(match_paths) == 0 or not match_path_regex:
            return True
        for pattern in match_paths:
            if re.search(pattern, path):
                return True
        return False

    yield from (operations.load_album(db, album_id, load_track_tags) for (album_id, path) in cursor if path_match_when_regex(path))
