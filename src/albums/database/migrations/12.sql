-- v12: Add stream_error to track, add album_other_file table

ALTER TABLE track ADD COLUMN stream_error TEXT NOT NULL DEFAULT '';
CREATE TABLE album_other_file (
    album_other_file_id INTEGER PRIMARY KEY,
    album_id REFERENCES album(album_id) ON UPDATE CASCADE ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    modify_timestamp INTEGER NOT NULL
);
CREATE INDEX idx_album_other_file_album_id ON album_other_file(album_id);
