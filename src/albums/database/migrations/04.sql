-- v4: Add embed_ix column to track_picture

ALTER TABLE track_picture ADD COLUMN embed_ix INTEGER NOT NULL DEFAULT 0;
