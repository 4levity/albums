-- v8: Add description column to track_picture

ALTER TABLE track_picture ADD COLUMN description TEXT NOT NULL DEFAULT '';
