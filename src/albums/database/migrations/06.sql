-- v6: Add cover_source column to album_picture_file

ALTER TABLE album_picture_file ADD COLUMN cover_source INTEGER NOT NULL DEFAULT 0;
