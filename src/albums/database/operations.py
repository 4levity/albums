import json
import logging
import sqlite3


logger = logging.getLogger(__name__)


def load_album(db: sqlite3.Connection, album_id: int, load_track_tag=True):
    row = db.execute("SELECT path FROM album WHERE album_id = ?;", (album_id,)).fetchone()
    if row is None:
        return None

    (path,) = row
    collections = [
        name
        for (name,) in db.execute(
            "SELECT collection_name FROM collection AS c JOIN album_collection AS ac ON c.collection_id = ac.collection_id WHERE ac.album_id = ?;",
            (album_id,),
        )
    ]
    tracks = _load_tracks(db, album_id, load_track_tag)

    # todo ignores
    return {"album_id": album_id, "path": path, "collections": collections, "tracks": tracks}


def add(db: sqlite3.Connection, album: dict):
    (album_id,) = db.execute("INSERT INTO album (path) VALUES (?) RETURNING album_id;", (album["path"],)).fetchone()
    _insert_collections(db, album_id, album.get("collections", []))
    _insert_tracks(db, album_id, album["tracks"])
    return album_id


def remove(db: sqlite3.Connection, album_id: int):
    cur = db.execute("DELETE FROM album WHERE album_id = ?;", (album_id,))
    if cur.rowcount == 0:
        logger.warning(f"didn't delete album, not found: {album_id}")


def update_collections(db: sqlite3.Connection, album_id: int, collections: list[str]):
    db.execute("DELETE FROM album_collection WHERE album_id = ?;", (album_id,))
    _insert_collections(db, album_id, collections)


def update_tracks(db: sqlite3.Connection, album_id: int, tracks: list[dict]):
    db.execute("DELETE FROM track WHERE album_id = ?;", (album_id,))
    _insert_tracks(db, album_id, tracks)


def _insert_tracks(db: sqlite3.Connection, album_id: int, tracks: list[dict]):
    for track in tracks:
        (track_id,) = db.execute(
            "INSERT INTO track ("
            "album_id, filename, file_size, modify_timestamp, stream_bitrate, stream_channels, stream_codec, stream_length, stream_sample_rate"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING track_id",
            (
                album_id,
                track["filename"],
                track["file_size"],
                track["modify_timestamp"],
                track.get("stream", {}).get("bitrate", 0),
                track.get("stream", {}).get("channels", 0),
                track.get("stream", {}).get("codec", "unknown"),
                track.get("stream", {}).get("length", 0),
                track.get("stream", {}).get("sample_rate", 0),
            ),
        ).fetchone()
        for name, value in track["tags"].items():
            db.execute("INSERT INTO track_tag (track_id, name, value_json) VALUES (?, ?, ?);", (track_id, name, json.dumps(value)))


def _load_tracks(db: sqlite3.Connection, album_id: int, load_tags=True):
    tracks = []
    for (
        track_id,
        filename,
        file_size,
        modify_timestamp,
        stream_bitrate,
        stream_channels,
        stream_codec,
        stream_length,
        stream_sample_rate,
    ) in db.execute(
        "SELECT track_id, filename, file_size, modify_timestamp, stream_bitrate, stream_channels, stream_codec, stream_length, stream_sample_rate "
        "FROM track WHERE album_id = ? ORDER BY filename ASC;",
        (album_id,),
    ):
        if load_tags:
            tags = dict(((k, json.loads(v)) for (k, v) in db.execute("SELECT name, value_json FROM track_tag WHERE track_id = ?;", (track_id,))))
        else:
            tags = {}
        stream = {
            "bitrate": stream_bitrate,
            "channels": stream_channels,
            "codec": stream_codec,
            "length": stream_length,
            "sample_rate": stream_sample_rate,
        }
        track = {"filename": filename, "file_size": file_size, "modify_timestamp": modify_timestamp, "stream": stream, "tags": tags}
        tracks.append(track)
    return tracks


def _insert_collections(db: sqlite3.Connection, album_id: int, collections: list[str]):
    for collection_name in collections:
        collection_id = _get_collection_id(db, collection_name)
        db.execute("INSERT INTO album_collection (album_id, collection_id) VALUES (?, ?);", (album_id, collection_id))


def _get_collection_id(db: sqlite3.Connection, collection_name: str):
    row = db.execute("SELECT collection_id FROM collection WHERE collection_name = ?;", (collection_name,)).fetchone()
    if row is None:
        row = db.execute("INSERT INTO collection (collection_name) VALUES (?) RETURNING collection_id;", (collection_name,)).fetchone()
    return row[0]
