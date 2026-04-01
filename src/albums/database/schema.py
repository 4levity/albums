import logging

from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from .orm import schema_table

logger = logging.getLogger(__name__)

SQL_INIT_SCHEMA = """
CREATE TABLE _schema (
    version INTEGER UNIQUE NOT NULL
);
INSERT INTO _schema (version) VALUES (1);

CREATE TABLE album (
    album_id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL
    -- v7 add column scanner
);
-- v7 add album.path index

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
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    modify_timestamp INTEGER NOT NULL,
    stream_bitrate INTEGER NOT NULL,
    stream_channels INTEGER NOT NULL,
    stream_codec TEXT NOT NULL,
    stream_length REAL NOT NULL,
    stream_sample_rate INTEGER NOT NULL
    -- v12 add stream_error
);
CREATE INDEX idx_track_album_id ON track(album_id);

CREATE TABLE track_tag (
    track_tag_id INTEGER PRIMARY KEY,
    track_id REFERENCES track(track_id) ON UPDATE CASCADE ON DELETE CASCADE,
    name TEXT NOT NULL,
    value TEXT NOT NULL
);
CREATE INDEX idx_track_tag_track_id ON track_tag(track_id);
"""

MIGRATIONS = {  # key is target schema version
    2: """
CREATE TABLE scan_history (
    scan_history_id INTEGER PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    folders_scanned INTEGER NOT NULL,
    albums_total INTEGER NOT NULL
);
CREATE INDEX idx_scan_history_timestamp ON scan_history(timestamp);
""",
    3: """
CREATE TABLE track_picture (
    track_picture_id INTEGER PRIMARY KEY,
    track_id REFERENCES track(track_id) ON UPDATE CASCADE ON DELETE CASCADE,
    picture_type INTEGER NOT NULL,
    format TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    -- v10 add column depth_bpp
    file_size INTEGER NOT NULL,
    file_hash BLOB NOT NULL,
    -- v4 add embed_ix
    -- v8 add description
    mismatch TEXT NULL -- v5 renamed to "load_issue"
);
CREATE INDEX idx_track_picture_track_id ON track_picture(track_id);

CREATE TABLE album_picture_file (
    album_picture_file_id INTEGER PRIMARY KEY,
    album_id REFERENCES album(album_id) ON UPDATE CASCADE ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    modify_timestamp INTEGER NOT NULL,
    file_hash BLOB NOT NULL,
    format TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL
    -- v10 add column depth_bpp
    -- v6 add column cover_source
);
CREATE INDEX idx_album_picture_file_album_id ON album_picture_file(album_id);
""",
    4: "ALTER TABLE track_picture ADD COLUMN embed_ix INTEGER NOT NULL DEFAULT 0;",
    5: "ALTER TABLE track_picture RENAME COLUMN mismatch TO load_issue;",
    6: "ALTER TABLE album_picture_file ADD COLUMN cover_source INTEGER NOT NULL DEFAULT 0;",
    7: """
CREATE UNIQUE INDEX album_path ON album(path);
ALTER TABLE album ADD COLUMN scanner INTEGER NOT NULL DEFAULT 0;
""",
    8: "ALTER TABLE track_picture ADD COLUMN description TEXT NOT NULL DEFAULT '';",
    9: """
CREATE TABLE setting (
    name TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
) WITHOUT ROWID;
""",
    10: """
ALTER TABLE album_picture_file ADD COLUMN depth_bpp INTEGER NOT NULL DEFAULT 0;
ALTER TABLE album_picture_file ADD COLUMN load_issue TEXT NULL;
ALTER TABLE track_picture ADD COLUMN depth_bpp INTEGER NOT NULL DEFAULT 0;
""",
    11: """
PRAGMA foreign_keys = OFF;
CREATE TABLE new_collection (
    collection_id INTEGER PRIMARY KEY,
    collection_name TEXT NOT NULL UNIQUE ON CONFLICT IGNORE
);
INSERT INTO new_collection (collection_id, collection_name) SELECT collection_id, collection_name from collection;
DROP TABLE collection;
ALTER TABLE new_collection RENAME TO collection;
PRAGMA foreign_keys = ON;
""",  # cannot alter column constraints in sqlite3
    12: """
ALTER TABLE track ADD COLUMN stream_error TEXT NOT NULL DEFAULT '';
CREATE TABLE album_other_file (
    album_other_file_id INTEGER PRIMARY KEY,
    album_id REFERENCES album(album_id) ON UPDATE CASCADE ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    modify_timestamp INTEGER NOT NULL
);
CREATE INDEX idx_album_other_file_album_id ON album_other_file(album_id);
""",
}

CURRENT_SCHEMA_VERSION = max(MIGRATIONS.keys())


def migrate(db: Engine, quiet: bool):
    with Session(db) as session:
        db_version = int(str(session.scalar(select(schema_table.c.version))))
    if db_version > CURRENT_SCHEMA_VERSION:
        raise RuntimeError(f"the database is newer than this version of albums ({db_version} > {CURRENT_SCHEMA_VERSION})")
    if db_version == CURRENT_SCHEMA_VERSION:
        return

    migrations = range(db_version + 1, CURRENT_SCHEMA_VERSION + 1)
    if not quiet:
        logger.debug(f"database schema version {db_version}, migrations to perform: {migrations}")
    for migration in migrations:
        if not quiet:
            logger.info(f"migrating database: v{migration}")
        with db.begin() as conn:
            connection = conn.connection
            connection.executescript(MIGRATIONS[migration])
    with Session(db) as session:
        session.execute(update(schema_table), {"version": CURRENT_SCHEMA_VERSION})
        session.commit()
