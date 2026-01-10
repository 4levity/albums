import json
import logging
import sqlite3


logger = logging.getLogger(__name__)

SQL_INIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS _schema (
    version INTEGER UNIQUE NOT NULL
);
INSERT INTO _schema (version) VALUES (1) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS album (
    album_id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS collection (
    collection_id INTEGER PRIMARY KEY,
    collection_name TEXT
);
CREATE TABLE IF NOT EXISTS album_collection (
    album_id INTEGER,
    collection_id INTEGER,
    FOREIGN KEY(album_id) REFERENCES album(album_id),
    FOREIGN KEY(collection_id) REFERENCES collection(collection_id)
);
CREATE TABLE IF NOT EXISTS album_ignore_check (
    album_id INTEGER,
    check_name TEXT,
    FOREIGN KEY(album_id) REFERENCES album(album_id)
);
CREATE TABLE IF NOT EXISTS track (
    track_id INTEGER PRIMARY KEY,
    album_id INTEGER NOT NULL,
    source_file TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    modify_date TEXT NOT NULL,
    metadata TEXT,
    FOREIGN KEY(album_id) REFERENCES album(album_id)
);
CREATE INDEX IF NOT EXISTS idx_track_album_id ON track (album_id);
"""

SQL_MIGRATION_SCRIPTS = []

SQL_CLEANUP = "DELETE FROM collection WHERE collection_id NOT IN (SELECT collection_id FROM album_collection);"


def migrate(db: sqlite3.Connection):
    # TODO check schema version, apply migration scripts, update version
    pass


def open(filename: str):
    db = sqlite3.connect(filename)
    db.executescript(SQL_INIT_SCHEMA) # TODO only do this when creating database
    migrate(db)
    db.executescript(SQL_CLEANUP)
    return db


def close(con: sqlite3.Connection):
    con.commit()
    con.close()
    logger.debug("closed database")


def load_tracks(con: sqlite3.Connection, album_id: int):
    tracks = []
    for source_file, file_size, modify_date, metadata in con.execute(
        "SELECT source_file, file_size, modify_date, metadata FROM track WHERE album_id = ? ORDER BY source_file ASC;", (album_id,)
    ):
        tracks.append(json.loads(metadata) | {"SourceFile": source_file, "FileSize": file_size, "FileModifyDate": modify_date})
    return tracks


def load(con: sqlite3.Connection):
    collections = {}
    for collection_row in con.execute("SELECT collection_id, collection_name FROM collection;"):
        collections[str(collection_row[0])] = collection_row[1]

    albums = {}
    for album_row in con.execute("SELECT path FROM album ORDER BY path;"):
        albums |= {album_row[0]: {"path": album_row[0], "tracks": [], "collections": []}}

    for row in con.execute("SELECT path, collection_id FROM album_collection AS ac JOIN album ON album.album_id = ac.album_id;"):
        albums[row[0]]["collections"].append(collections[str(row[1])])

    # todo ignores
    for row in con.execute(
        "SELECT path, source_file, file_size, modify_date, metadata FROM track JOIN album ON album.album_id = track.album_id ORDER BY source_file ASC;"
    ):
        albums[row[0]]["tracks"].append(json.loads(row[4]) | {"SourceFile": row[1], "FileSize": row[2], "FileModifyDate": row[3]})
    return albums


def get_collection_id(con: sqlite3.Connection, collection_name: str):
    cur = con.execute("SELECT collection_id FROM collection WHERE collection_name = ?;", (collection_name,))
    found = cur.fetchone()
    if found is not None:
        return found[0]
    else:
        cur = con.execute("INSERT INTO collection (collection_name) VALUES (?) RETURNING collection_id;", (collection_name,))
        return cur.fetchone()[0]


def get_album_id(con: sqlite3.Connection, path: str):
    cur = con.execute("SELECT album_id FROM album WHERE path = ?", (path,))
    album_id = cur.fetchone()[0]
    return album_id


def insert_album_details(con: sqlite3.Connection, album: dict):
    album_id = get_album_id(con, album["path"])
    collection_ids = {}
    for collection_name in album.get("collections", []):
        if collection_name not in collection_ids:
            collection_ids[collection_name] = get_collection_id(con, collection_name)
        con.execute("INSERT INTO album_collection (album_id, collection_id) VALUES (?, ?);", (album_id, collection_ids[collection_name]))
    for track in album["tracks"]:
        metadata = {key: value for key, value in track.items() if key not in ["SourceFile", "FileSize", "FileModifyDate"]}
        con.execute(
            "INSERT INTO track (album_id, source_file, file_size, modify_date, metadata) VALUES (?, ?, ?, ?, ?);",
            (album_id, track["SourceFile"], track["FileSize"], track["FileModifyDate"], json.dumps(metadata)),
        )


def add(con: sqlite3.Connection, album: dict):
    con.execute("INSERT INTO album (path) VALUES (?);", (album["path"],))
    insert_album_details(con, album)


def delete_album_details(con: sqlite3.Connection, path: str):
    album_id = get_album_id(con, path)
    con.execute("DELETE FROM track WHERE album_id = ?;", (album_id,))
    con.execute("DELETE FROM album_ignore_check WHERE album_id = ?;", (album_id,))
    con.execute("DELETE FROM album_collection WHERE album_id = ?;", (album_id,))


def remove(con: sqlite3.Connection, path: str):
    delete_album_details(con, path)
    cur = con.execute("DELETE FROM album WHERE path = ?;", (path,))
    if cur.rowcount == 0:
        logger.warning(f"didn't delete album, not found: {path}")


def update(con: sqlite3.Connection, album: dict):
    delete_album_details(con, album["path"])
    insert_album_details(con, album)
