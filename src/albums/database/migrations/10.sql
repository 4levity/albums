-- v10: Add depth_bpp and load_issue columns to picture tables

ALTER TABLE album_picture_file ADD COLUMN depth_bpp INTEGER NOT NULL DEFAULT 0;
ALTER TABLE album_picture_file ADD COLUMN load_issue TEXT NULL;
ALTER TABLE track_picture ADD COLUMN depth_bpp INTEGER NOT NULL DEFAULT 0;
