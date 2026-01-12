import json
import logging
from pathlib import Path
import sqlite3


logger = logging.getLogger(__name__)

SQL_INIT_SCHEMA = """
CREATE TABLE _schema (
    version INTEGER UNIQUE NOT NULL
);
INSERT INTO _schema (version) VALUES (1);

CREATE TABLE album (
    album_id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL
);

CREATE TABLE collection (
    collection_id INTEGER PRIMARY KEY,
    collection_name TEXT UNIQUE NOT NULL
);

CREATE TABLE album_collection (
    album_collection_id INTEGER PRIMARY KEY,
    album_id REFERENCES album(album_id) ON UPDATE CASCADE ON DELETE CASCADE,
    collection_id REFERENCES collection(collection_id) ON UPDATE CASCADE ON DELETE CASCADE
);
CREATE INDEX idx_collection_by_album_id ON album_collection(album_id);
CREATE INDEX idx_collection_by_collection_id ON album_collection(collection_id);

CREATE TABLE album_ignore_check (
    album_ignore_check_id INTEGER PRIMARY KEY,
    album_id REFERENCES album(album_id) ON UPDATE CASCADE ON DELETE CASCADE,
    check_name TEXT NOT NULL
);
CREATE INDEX idx_ignore_check_album_id ON album_ignore_check(album_id);

CREATE TABLE track (
    track_id INTEGER PRIMARY KEY,
    album_id REFERENCES album(album_id) ON UPDATE CASCADE ON DELETE CASCADE,
    source_file TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    modify_timestamp INTEGER NOT NULL
);
CREATE INDEX idx_track_album_id ON track(album_id);

CREATE TABLE track_metadata (
    track_metdata_id INTEGER PRIMARY KEY,
    track_id REFERENCES track(track_id) ON UPDATE CASCADE ON DELETE CASCADE,
    name TEXT NOT NULL,
    value_json TEXT NOT NULL
);
CREATE INDEX idx_metadata_track_id ON track_metadata(track_id);
"""

SQL_INIT_CONNECTION = """
PRAGMA foreign_keys = ON;
"""

SQL_MIGRATION_SCRIPTS = []

SQL_CLEANUP = "DELETE FROM collection WHERE collection_id NOT IN (SELECT collection_id FROM album_collection);"


def migrate(db: sqlite3.Connection):
    # TODO check schema version, apply migration scripts, update version
    pass


def open(filename: str):
    new_database = filename == ":memory:" or not Path(filename).exists()

    # TODO switch to explicit transactions
    db = sqlite3.connect(filename)
    db.executescript(SQL_INIT_CONNECTION)
    if new_database:
        print(f"creating database {filename}")
        db.executescript(SQL_INIT_SCHEMA)

    migrate(db)
    db.executescript(SQL_CLEANUP)
    return db


def close(con: sqlite3.Connection):
    con.commit()
    con.close()
    logger.debug("closed database")


def load_tracks(con: sqlite3.Connection, album_id: int, load_metadata=True):
    tracks = []
    for track_id, source_file, file_size, modify_timestamp in con.execute(
        "SELECT track_id, source_file, file_size, modify_timestamp FROM track WHERE album_id = ? ORDER BY source_file ASC;", (album_id,)
    ):
        if load_metadata:
            metadata = dict(
                ((k, json.loads(v)) for (k, v) in con.execute("SELECT name, value_json FROM track_metadata WHERE track_id = ?;", (track_id,)))
            )
        else:
            metadata = {}
        track = {"source_file": source_file, "file_size": file_size, "modify_timestamp": modify_timestamp, "metadata": metadata}
        tracks.append(track)
    return tracks


def load_album(con: sqlite3.Connection, album_id: int, load_track_metadata=True):
    row = con.execute("SELECT path FROM album WHERE album_id = ?;", (album_id,)).fetchone()
    if row is None:
        return None

    (path,) = row
    collections = [
        name
        for (name,) in con.execute(
            "SELECT collection_name FROM collection AS c JOIN album_collection AS ac ON c.collection_id = ac.collection_id WHERE ac.album_id = ?;",
            (album_id,),
        )
    ]
    tracks = load_tracks(con, album_id, load_track_metadata)

    # todo ignores
    return {"album_id": album_id, "path": path, "collections": collections, "tracks": tracks}


def get_collection_id(con: sqlite3.Connection, collection_name: str):
    row = con.execute("SELECT collection_id FROM collection WHERE collection_name = ?;", (collection_name,)).fetchone()
    if row is None:
        row = con.execute("INSERT INTO collection (collection_name) VALUES (?) RETURNING collection_id;", (collection_name,)).fetchone()
    return row[0]


def get_album_id(con: sqlite3.Connection, path: str):
    cur = con.execute("SELECT album_id FROM album WHERE path = ?;", (path,))
    album_id = cur.fetchone()[0]
    return album_id


def insert_tracks(con: sqlite3.Connection, album_id: int, tracks: list[dict]):
    for track in tracks:
        (track_id,) = con.execute(
            "INSERT INTO track (album_id, source_file, file_size, modify_timestamp) VALUES (?, ?, ?, ?) RETURNING track_id",
            (album_id, track["source_file"], track["file_size"], track["modify_timestamp"]),
        ).fetchone()
        for name, value in track["metadata"].items():
            con.execute("INSERT INTO track_metadata (track_id, name, value_json) VALUES (?, ?, ?);", (track_id, name, json.dumps(value)))


def insert_collections(con: sqlite3.Connection, album_id: int, collections: list[str]):
    for collection_name in collections:
        collection_id = get_collection_id(con, collection_name)
        con.execute("INSERT INTO album_collection (album_id, collection_id) VALUES (?, ?);", (album_id, collection_id))


def add(con: sqlite3.Connection, album: dict):
    (album_id,) = con.execute("INSERT INTO album (path) VALUES (?) RETURNING album_id;", (album["path"],)).fetchone()
    insert_collections(con, album_id, album.get("collections", []))
    insert_tracks(con, album_id, album["tracks"])
    return album_id


def remove(con: sqlite3.Connection, album_id: int):
    cur = con.execute("DELETE FROM album WHERE album_id = ?;", (album_id,))
    if cur.rowcount == 0:
        logger.warning(f"didn't delete album, not found: {album_id}")


def update_collections(con: sqlite3.Connection, album_id: int, collections: list[str]):
    con.execute("DELETE FROM album_collection WHERE album_id = ?;", (album_id,))
    insert_collections(con, album_id, collections)


def update_tracks(con: sqlite3.Connection, album_id: int, tracks: list[dict]):
    con.execute("DELETE FROM track WHERE album_id = ?;", (album_id,))
    insert_tracks(con, album_id, tracks)
