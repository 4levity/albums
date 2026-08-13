-- v11: Make collection_name use ON CONFLICT IGNORE (cannot alter column constraints in sqlite3)
-- Recreate the collection table with the relaxed unique constraint

PRAGMA foreign_keys = OFF;
CREATE TABLE new_collection (
    collection_id INTEGER PRIMARY KEY,
    collection_name TEXT NOT NULL UNIQUE ON CONFLICT IGNORE
);
INSERT INTO new_collection (collection_id, collection_name) SELECT collection_id, collection_name from collection;
DROP TABLE collection;
ALTER TABLE new_collection RENAME TO collection;
PRAGMA foreign_keys = ON;
