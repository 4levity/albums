-- v13: Add stream_bits_per_sample to track

ALTER TABLE track ADD COLUMN stream_bits_per_sample INTEGER NOT NULL DEFAULT 0;
