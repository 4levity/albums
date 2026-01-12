import re
import sqlite3
from . import operations


def select_albums(db: sqlite3.Connection, collection_names: list[str], match_paths: list[str], match_path_regex: bool, load_track_metadata=True):
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
                match_paths + collection_names,
            )

    def path_match_when_regex(path: str):
        if len(match_paths) == 0 or not match_path_regex:
            return True
        for pattern in match_paths:
            if re.search(pattern, path):
                return True
        return False

    yield from (operations.load_album(db, album_id, load_track_metadata) for (album_id, path) in cursor if path_match_when_regex(path))
