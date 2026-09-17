-- v20: Add library_folder: the folders seen during the last full library scan
--
-- Every folder the scanner walks (album and non-album alike) is stored by (parent_path, name),
-- with the name also casefolded (name_cf), so checks can find sibling folders that differ
-- only in case from the database alone. The table is rebuilt by each full scan.
CREATE TABLE library_folder (
    library_folder_id INTEGER PRIMARY KEY,
    parent_path TEXT NOT NULL,
    name TEXT NOT NULL,
    name_cf TEXT NOT NULL
);
CREATE UNIQUE INDEX library_folder_path ON library_folder (parent_path, name);
CREATE INDEX idx_library_folder_cf ON library_folder (parent_path, name_cf, name);
