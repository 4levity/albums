-- v11: Make collection_name use ON CONFLICT IGNORE (cannot alter column constraints in sqlite3)
-- Recreate the collection table with the relaxed unique constraint
--
-- The PRAGMA foreign_keys toggle is essential: album_collection has foreign keys to
-- collection, and with foreign key enforcement ON the DROP TABLE below would cascade and
-- delete all album_collection rows.  Note this migration is therefore not atomic (the
-- pragma cannot be changed inside a transaction); if it fails partway, the data remains
-- intact in the original collection table or in new_collection and can be recovered manually.

PRAGMA foreign_keys = OFF;
CREATE TABLE new_collection (
    collection_id INTEGER PRIMARY KEY,
    collection_name TEXT NOT NULL UNIQUE ON CONFLICT IGNORE
);
INSERT INTO new_collection (collection_id, collection_name) SELECT collection_id, collection_name from collection;
DROP TABLE collection;
ALTER TABLE new_collection RENAME TO collection;
PRAGMA foreign_keys = ON;
