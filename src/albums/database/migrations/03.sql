-- v3: Add track_picture and album_picture_file tables

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
