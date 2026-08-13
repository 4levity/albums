-- v16: Migrate legacy vorbis comment tag names to canonical BasicField field names
-- Record presence of legacy fields in track_legacy_tag for tracking purposes

INSERT INTO track_legacy_tag (track_id, tag_name)
SELECT DISTINCT tt.track_id, tt.name FROM track_tag tt
WHERE tt.name IN ('album artist', 'label', 'publisher', 'totaldiscs')
AND NOT EXISTS (
    SELECT 1 FROM track_legacy_tag lt
    WHERE lt.track_id = tt.track_id AND lt.tag_name = tt.name
);

-- Migrate "album artist" values to canonical "albumartist"
INSERT INTO track_tag (track_id, name, value)
SELECT tt.track_id, 'albumartist', tt.value FROM track_tag tt
WHERE tt.name = 'album artist'
AND NOT EXISTS (
    SELECT 1 FROM track_tag tt2
    WHERE tt2.track_id = tt.track_id AND tt2.name = 'albumartist' AND tt2.value = tt.value
);

-- Migrate "label" and "publisher" values to canonical "organization"
INSERT INTO track_tag (track_id, name, value)
SELECT tt.track_id, 'organization', tt.value FROM track_tag tt
WHERE tt.name IN ('label', 'publisher')
AND NOT EXISTS (
    SELECT 1 FROM track_tag tt2
    WHERE tt2.track_id = tt.track_id AND tt2.name = 'organization' AND tt2.value = tt.value
);

-- Migrate "totaldiscs" values to canonical "disctotal"
INSERT INTO track_tag (track_id, name, value)
SELECT tt.track_id, 'disctotal', tt.value FROM track_tag tt
WHERE tt.name = 'totaldiscs'
AND NOT EXISTS (
    SELECT 1 FROM track_tag tt2
    WHERE tt2.track_id = tt.track_id AND tt2.name = 'disctotal' AND tt2.value = tt.value
);

-- Remove legacy tag entries from track_tag
DELETE FROM track_tag
WHERE name IN ('album artist', 'label', 'publisher', 'totaldiscs');
