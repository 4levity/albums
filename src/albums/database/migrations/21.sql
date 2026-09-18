-- v21: Store each track's fields as a JSON object on the track row and drop the per-value rows
--
-- Field values are always read and written as a whole-track blob, so fold the track_field rows
-- into a single JSON object per track mapping field name to a list of values,
-- e.g. {"album": ["The Grand Design"], "genre": ["Post Rock"]}.
--
-- SQLite disallows an aggregate function inside another (json_group_object(..., json_group_array(...))),
-- so build one "name": [...] fragment per field in a subquery grouped by name, then concatenate.
--
-- Wrapped in an explicit transaction: executescript() does not run inside the caller's
-- transaction (it commits it first), so without BEGIN/COMMIT the statements would be
-- auto-committed one by one.
BEGIN;
ALTER TABLE track ADD COLUMN fields_json TEXT NOT NULL DEFAULT '{}';
UPDATE track SET fields_json = COALESCE((
    SELECT '{' || group_concat(fragment, ',') || '}'
    FROM (
        SELECT '"' || name || '":' || json_group_array(value) AS fragment
        FROM track_field
        WHERE track_field.track_id = track.track_id
        GROUP BY name
    )
), '{}');
DROP INDEX idx_track_field_track_id;
DROP TABLE track_field;
COMMIT;
