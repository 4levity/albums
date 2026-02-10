import json
import logging
import sqlite3

from ..checks.all import ALL_CHECK_NAMES
from ..library.picture import picture_type_from_filename
from ..types import Album, Picture, PictureType, ScanHistoryEntry, Stream, Track

logger = logging.getLogger(__name__)

PICTURE_TYPE_FRONT_COVER_SOURCE_FILE = 200


def load_album(db: sqlite3.Connection, album_id: int, load_track_tag: bool = True) -> Album:
    with db:
        row = db.execute("SELECT path FROM album WHERE album_id = ?;", (album_id,)).fetchone()
        if row is None:
            raise ValueError(f"load_album called with invalid album_id={album_id}")

        (path,) = row
        collections = [
            name
            for (name,) in db.execute(
                "SELECT collection_name FROM collection AS c JOIN album_collection AS ac ON c.collection_id = ac.collection_id WHERE ac.album_id = ?;",
                (album_id,),
            )
        ]

        ignore_checks: list[str] = []
        for (name,) in db.execute("SELECT check_name FROM album_ignore_check WHERE album_id = ?;", (album_id,)):
            if name in ALL_CHECK_NAMES:
                ignore_checks.append(name)
            else:
                # if chack_names changed, a migrationm should have prevented this, but raising an error here will not solve anything
                logger.warning(f'album_id {album_id} has unknown check_name "{name}" in ignore list')

        tracks = list(_load_tracks(db, album_id, load_track_tag))
        picture_files: dict[str, Picture] = dict(
            (
                filename,
                Picture(
                    picture_type_from_filename(filename), format, width, height, file_size, file_hash, None, modify_timestamp, 0, bool(cover_source)
                ),
            )
            for (filename, file_size, modify_timestamp, file_hash, format, width, height, cover_source) in db.execute(
                "SELECT filename, file_size, modify_timestamp, file_hash, format, width, height, cover_source FROM album_picture_file WHERE album_id = ? ORDER BY filename;",
                (album_id,),
            )
        )
        return Album(path, tracks, collections, ignore_checks, picture_files, album_id)


def add(db: sqlite3.Connection, album: Album) -> int:
    with db:
        (album_id,) = db.execute("INSERT INTO album (path) VALUES (?) RETURNING album_id;", (album.path,)).fetchone()
        _insert_collections(db, album_id, album.collections)
        _insert_ignore_checks(db, album_id, album.ignore_checks)
        _insert_tracks(db, album_id, album.tracks)
        _insert_picture_files(db, album_id, album.picture_files)
        return album_id


def remove(db: sqlite3.Connection, album_id: int):
    with db:
        cur = db.execute("DELETE FROM album WHERE album_id = ?;", (album_id,))
        if cur.rowcount == 0:
            logger.warning(f"didn't delete album, not found: {album_id}")


def update_collections(db: sqlite3.Connection, album_id: int, collections: list[str]):
    with db:
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
    with db:
        db.execute("DELETE FROM album_ignore_check WHERE album_id = ?;", (album_id,))
        _insert_ignore_checks(db, album_id, ignore_checks)


def _insert_ignore_checks(db: sqlite3.Connection, album_id: int, ignore_checks: list[str]):
    for check_name in ignore_checks:
        if check_name not in ALL_CHECK_NAMES:
            raise ValueError(f"check_name {check_name} is not valid")
        db.execute("INSERT INTO album_ignore_check (album_id, check_name) VALUES (?, ?);", (album_id, check_name))


def update_tracks(db: sqlite3.Connection, album_id: int, tracks: list[Track]):
    with db:
        db.execute("DELETE FROM track WHERE album_id = ?;", (album_id,))
        _insert_tracks(db, album_id, tracks)


def _insert_tracks(db: sqlite3.Connection, album_id: int, tracks: list[Track]):
    for track in tracks:
        if not track.stream:
            raise ValueError(f"can't save track without stream info: {track.filename}")
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
        for picture in track.pictures:
            db.execute(
                "INSERT INTO track_picture (track_id, picture_type, format, width, height, file_size, file_hash, load_issue, embed_ix) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                (
                    track_id,
                    picture.picture_type.value,
                    picture.format,
                    picture.width,
                    picture.height,
                    picture.file_size,
                    picture.file_hash,
                    json.dumps(picture.load_issue) if picture.load_issue else None,
                    picture.embed_ix,
                ),
            )


def update_picture_files(db: sqlite3.Connection, album_id: int, picture_files: dict[str, Picture]):
    with db:
        db.execute("DELETE FROM album_picture_file WHERE album_id = ?;", (album_id,))
        _insert_picture_files(db, album_id, picture_files)


def _insert_picture_files(db: sqlite3.Connection, album_id: int, picture_files: dict[str, Picture]):
    for filename, picture in picture_files.items():
        db.execute(
            "INSERT INTO album_picture_file (album_id, filename, file_size, modify_timestamp, file_hash, format, width, height, cover_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                album_id,
                filename,
                picture.file_size,
                picture.modify_timestamp,
                picture.file_hash,
                picture.format,
                picture.width,
                picture.height,
                1 if picture.front_cover_source else 0,
            ),
        )


def _load_tracks(db: sqlite3.Connection, album_id: int, load_tags: bool = True):
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
            pictures = _load_pictures(db, track_id)
        else:
            tags = {}
            pictures = []
        stream = Stream(stream_length, stream_bitrate, stream_channels, stream_codec, stream_sample_rate)
        track = Track(filename, tags, file_size, modify_timestamp, stream, pictures)
        yield track


def _load_tags(db: sqlite3.Connection, track_id: int):
    tags: dict[str, list[str]] = {}
    for name, value in db.execute("SELECT name, value FROM track_tag WHERE track_id = ?;", (track_id,)):
        tags.setdefault(name, []).append(value)
    return tags


def _load_pictures(db: sqlite3.Connection, track_id: int):
    return [
        Picture(
            PictureType(picture_type), format, width, height, file_size, file_hash, json.loads(load_issue) if load_issue else None, None, embed_ix
        )
        for picture_type, format, width, height, file_size, file_hash, load_issue, embed_ix in db.execute(
            "SELECT picture_type, format, width, height, file_size, file_hash, load_issue, embed_ix FROM track_picture WHERE track_id = ? ORDER BY picture_type;",
            (track_id,),
        )
    ]


def record_full_scan(db: sqlite3.Connection, entry: ScanHistoryEntry):
    with db:
        db.execute(
            "INSERT INTO scan_history (timestamp, folders_scanned, albums_total) VALUES (?, ?, ?)",
            (entry.timestamp, entry.folders_scanned, entry.albums_total),
        )


def get_last_scan_info(db: sqlite3.Connection) -> ScanHistoryEntry | None:
    row = db.execute("SELECT timestamp, folders_scanned, albums_total FROM scan_history ORDER BY timestamp DESC LIMIT 1;").fetchone()
    if row is None:
        return None
    (timestamp, folders_scanned, albums_total) = row
    return ScanHistoryEntry(timestamp, folders_scanned, albums_total)
