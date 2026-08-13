-- v14: Add created_at and modified_at timestamps to album

ALTER TABLE album ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0;
ALTER TABLE album ADD COLUMN modified_at INTEGER NOT NULL DEFAULT 0;
