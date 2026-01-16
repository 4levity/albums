import logging
import sqlite3
from ..types import Album, Stream, Track


logger = logging.getLogger(__name__)


def load_album(db: sqlite3.Connection, album_id: int, load_track_tag=True) -> Album:
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
    ignore_checks = [
        name
        for (name,) in db.execute(
            "SELECT check_name FROM album_ignore_check WHERE album_id = ?;",
            (album_id,),
        )
    ]
    tracks = list(_load_tracks(db, album_id, load_track_tag))

    # todo ignores
    return Album(path, tracks, collections, ignore_checks, album_id)


def add(db: sqlite3.Connection, album: Album) -> int:
    (album_id,) = db.execute("INSERT INTO album (path) VALUES (?) RETURNING album_id;", (album.path,)).fetchone()
    _insert_collections(db, album_id, album.collections)
    _insert_ignore_checks(db, album_id, album.ignore_checks)
    _insert_tracks(db, album_id, album.tracks)
    return album_id


def remove(db: sqlite3.Connection, album_id: int):
    cur = db.execute("DELETE FROM album WHERE album_id = ?;", (album_id,))
    if cur.rowcount == 0:
        logger.warning(f"didn't delete album, not found: {album_id}")


def update_collections(db: sqlite3.Connection, album_id: int, collections: list[str]):
    db.execute("DELETE FROM album_collection WHERE album_id = ?;", (album_id,))
    _insert_collections(db, album_id, collections)


def _insert_collections(db: sqlite3.Connection, album_id: int, collections: list[str]):
    for collection_name in collections:
        collection_id = _get_collection_id(db, collection_name)
        db.execute("INSERT INTO album_collection (album_id, collection_id) VALUES (?, ?);", (album_id, collection_id))


def _get_collection_id(db: sqlite3.Connection, collection_name: str):
    row = db.execute("SELECT collection_id FROM collection WHERE collection_name = ?;", (collection_name,)).fetchone()
    if row is None:
        row = db.execute("INSERT INTO collection (collection_name) VALUES (?) RETURNING collection_id;", (collection_name,)).fetchone()
    return row[0]


def update_ignore_checks(db: sqlite3.Connection, album_id: int, ignore_checks: list[str]):
    db.execute("DELETE FROM album_ignore_check WHERE album_id = ?;", (album_id,))
    _insert_ignore_checks(db, album_id, ignore_checks)


def _insert_ignore_checks(db: sqlite3.Connection, album_id: int, ignore_checks: list[str]):
    # TODO ensure valid names
    for check_name in ignore_checks:
        db.execute("INSERT INTO album_ignore_check (album_id, check_name) VALUES (?, ?);", (album_id, check_name))


def update_tracks(db: sqlite3.Connection, album_id: int, tracks: list[Track]):
    db.execute("DELETE FROM track WHERE album_id = ?;", (album_id,))
    _insert_tracks(db, album_id, tracks)


def _insert_tracks(db: sqlite3.Connection, album_id: int, tracks: list[Track]):
    for track in tracks:
        (track_id,) = db.execute(
            "INSERT INTO track ("
            "album_id, filename, file_size, modify_timestamp, stream_bitrate, stream_channels, stream_codec, stream_length, stream_sample_rate"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING track_id",
            (
                album_id,
                track.filename,
                track.file_size,
                track.modify_timestamp,
                track.stream.bitrate,
                track.stream.channels,
                track.stream.codec,
                track.stream.length,
                track.stream.sample_rate,
            ),
        ).fetchone()
        for name, values in track.tags.items():
            for value in values:
                db.execute("INSERT INTO track_tag (track_id, name, value) VALUES (?, ?, ?);", (track_id, name, value))


def _load_tracks(db: sqlite3.Connection, album_id: int, load_tags=True):
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
            tags = _load_tags(db, track_id)
        else:
            tags = {}
        stream = Stream(stream_length, stream_bitrate, stream_channels, stream_codec, stream_sample_rate)
        track = Track(filename, tags, file_size, modify_timestamp, stream)
        yield track


def _load_tags(db: sqlite3.Connection, track_id: int):
    tags: dict[str, list[str]] = {}
    for name, value in db.execute("SELECT name, value FROM track_tag WHERE track_id = ?;", (track_id,)):
        tags.setdefault(name, []).append(value)
    return tags
