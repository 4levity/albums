-- v22: Rename check duplicate-pathname -> duplicate-filename

-- The name is easily confused with the duplicate-folder-name check, which
-- deals with folders, not filenames. Rename the stored settings (keys like
-- 'duplicate-pathname.enabled') and per-album ignores to the new name.
UPDATE album_ignore_check SET check_name = 'duplicate-filename' WHERE check_name = 'duplicate-pathname';
UPDATE setting SET name = REPLACE(name, 'duplicate-pathname.', 'duplicate-filename.') WHERE name LIKE 'duplicate-pathname.%';
