-- v15: Add track_legacy_tag table for tracking legacy vorbis comment field names

CREATE TABLE track_legacy_tag (
    track_legacy_tag_id INTEGER PRIMARY KEY,
    track_id REFERENCES track(track_id) ON UPDATE CASCADE ON DELETE CASCADE,
    tag_name TEXT NOT NULL
);
CREATE INDEX idx_legacy_tag_track_id ON track_legacy_tag(track_id);
