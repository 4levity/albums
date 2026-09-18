-- v21: Store each track's fields as a JSON object on the track row and drop the per-value rows
--
-- Field values are always read and written as a whole-track blob, so fold the track_field rows
-- into a single JSON object per track mapping field name to a list of values,
-- e.g. {"album": ["The Grand Design"], "genre": ["Post Rock"]}.
--
-- SQLite disallows an aggregate function inside another (json_group_object(..., json_group_array(...))),
-- so build one "name": [...] fragment per field in a subquery grouped by (track_id, name), then
-- concatenate the fragments per track.
--
-- The aggregation must run once over the whole table rather than as a correlated subquery in the
-- UPDATE: the planner cannot use idx_track_field_track_id through the nested subquery, so each
-- track would re-scan every row of track_field (minutes for a large library). Instead, aggregate
-- into a temporary table, then join it back by primary key with UPDATE ... FROM (SQLite 3.33+).
-- Tracks without fields keep the '{}' default from the ALTER.
--
-- Wrapped in an explicit transaction: executescript() does not run inside the caller's
-- transaction (it commits it first), so without BEGIN/COMMIT the statements would be
-- auto-committed one by one.
BEGIN;
ALTER TABLE track ADD COLUMN fields_json TEXT NOT NULL DEFAULT '{}';
CREATE TEMP TABLE track_fields_json AS
SELECT track_id, '{' || group_concat(fragment, ',') || '}' AS fields_json
FROM (
    SELECT track_id, '"' || name || '":' || json_group_array(value) AS fragment
    FROM track_field
    GROUP BY track_id, name
)
GROUP BY track_id;
UPDATE track
SET fields_json = track_fields_json.fields_json
FROM track_fields_json
WHERE track_fields_json.track_id = track.track_id;
DROP TABLE track_fields_json;
DROP INDEX idx_track_field_track_id;
DROP TABLE track_field;
COMMIT;
