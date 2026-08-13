-- v7: Add unique index on album.path and add scanner column

CREATE UNIQUE INDEX album_path ON album(path);
ALTER TABLE album ADD COLUMN scanner INTEGER NOT NULL DEFAULT 0;
