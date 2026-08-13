-- v5: Rename mismatch to load_issue in track_picture

ALTER TABLE track_picture RENAME COLUMN mismatch TO load_issue;
