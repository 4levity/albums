-- v18: Rename tables track_tag -> track_field and track_legacy_tag -> track_legacy_field

PRAGMA foreign_keys = OFF;
DROP INDEX idx_track_tag_track_id;
CREATE TABLE track_field (
    track_field_id INTEGER PRIMARY KEY,
    track_id REFERENCES track(track_id) ON UPDATE CASCADE ON DELETE CASCADE,
    name TEXT NOT NULL,
    value TEXT NOT NULL
);
INSERT INTO track_field (track_id, name, value) SELECT track_id, name, value FROM track_tag;
DROP TABLE track_tag;
CREATE INDEX idx_track_field_track_id ON track_field(track_id);

-- Rename table track_legacy_tag -> track_legacy_field + rename column tag_name -> field_name + rename PK column
DROP INDEX idx_legacy_tag_track_id;
CREATE TABLE track_legacy_field (
    track_legacy_field_id INTEGER PRIMARY KEY,
    track_id REFERENCES track(track_id) ON UPDATE CASCADE ON DELETE CASCADE,
    field_name TEXT NOT NULL
);
INSERT INTO track_legacy_field (track_id, field_name) SELECT track_id, tag_name FROM track_legacy_tag;
DROP TABLE track_legacy_tag;
CREATE INDEX idx_legacy_field_track_id ON track_legacy_field(track_id);

PRAGMA foreign_keys = ON;
