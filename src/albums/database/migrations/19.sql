-- v19: Remove ignored checks that are implicitly ignored because they depend on an ignored check
--
-- When a check is ignored for an album, every check that depends on it, directly or transitively,
-- cannot run and is ignored implicitly, so explicit ignore rows for them are redundant and are
-- deleted. The dependency pairs below must match the must_pass_checks of the checks in
-- src/albums/checks/all.py (the test in tests/database/migrations/test_migration19.py enforces this).
--
-- Wrapped in an explicit transaction: executescript() does not run inside the caller's
-- transaction (it commits it first), so without BEGIN/COMMIT the statements would be
-- auto-committed one by one.
BEGIN;
CREATE TEMP TABLE _check_dep (child TEXT NOT NULL, parent TEXT NOT NULL);
INSERT INTO _check_dep (child, parent) VALUES
    ('file-extension', 'illegal-pathname'),
    ('disc-in-track-number', 'legacy-fields'),
    ('invalid-track-or-disc-number', 'disc-in-track-number'),
    ('disc-numbering', 'invalid-track-or-disc-number'),
    ('disc-numbering', 'legacy-fields'),
    ('track-numbering', 'disc-numbering'),
    ('zero-pad-numbers', 'invalid-track-or-disc-number'),
    ('album-artist', 'legacy-fields'),
    ('artist', 'album-artist'),
    ('duplicate-album', 'album'),
    ('duplicate-album', 'artist'),
    ('publisher', 'legacy-fields'),
    ('album-sort', 'album'),
    ('album-artist-sort', 'album-artist'),
    ('artist-sort', 'artist'),
    ('compilation', 'artist'),
    ('duplicate-image', 'invalid-image'),
    ('picture-metadata', 'invalid-image'),
    ('album-art', 'invalid-image'),
    ('cover-available', 'duplicate-image'),
    ('cover-unique', 'duplicate-image'),
    ('conflicting-embedded', 'duplicate-image'),
    ('cover-dimensions', 'cover-available'),
    ('cover-embedded', 'conflicting-embedded'),
    ('folder-name', 'album'),
    ('folder-name', 'artist'),
    ('track-filename', 'album-artist'),
    ('track-filename', 'artist'),
    ('track-filename', 'track-numbering'),
    ('track-filename', 'track-title');
CREATE TEMP TABLE _redundant AS
WITH RECURSIVE _reach(child, ancestor) AS (
    SELECT child, parent FROM _check_dep
    UNION
    SELECT r.child, d.parent FROM _reach r JOIN _check_dep d ON d.child = r.ancestor
)
SELECT aic.album_id, aic.check_name
FROM album_ignore_check aic
JOIN _reach r ON r.child = aic.check_name
JOIN album_ignore_check other ON other.album_id = aic.album_id AND other.check_name = r.ancestor;
DELETE FROM album_ignore_check
WHERE (album_id, check_name) IN (SELECT album_id, check_name FROM _redundant);
DROP TABLE _redundant;
DROP TABLE _check_dep;
COMMIT;
