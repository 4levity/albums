CURRENT_SCHEMA_VERSION = 1

SQL_INIT_SCHEMA = f"""
CREATE TABLE _schema (
    version INTEGER UNIQUE NOT NULL
);
INSERT INTO _schema (version) VALUES ({CURRENT_SCHEMA_VERSION});

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
    modify_timestamp INTEGER NOT NULL,
    stream_bitrate INTEGER NOT NULL,
    stream_channels INTEGER NOT NULL,
    stream_codec TEXT NOT NULL,
    stream_length REAL NOT NULL,
    stream_sample_rate INTEGER NOT NULL
);
CREATE INDEX idx_track_album_id ON track(album_id);

CREATE TABLE track_tag (
    track_metdata_id INTEGER PRIMARY KEY,
    track_id REFERENCES track(track_id) ON UPDATE CASCADE ON DELETE CASCADE,
    name TEXT NOT NULL,
    value_json TEXT NOT NULL
);
CREATE INDEX idx_metadata_track_id ON track_tag(track_id);
"""
