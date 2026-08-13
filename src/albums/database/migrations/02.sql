-- v2: Add scan_history table

CREATE TABLE scan_history (
    scan_history_id INTEGER PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    folders_scanned INTEGER NOT NULL,
    albums_total INTEGER NOT NULL
);
CREATE INDEX idx_scan_history_timestamp ON scan_history(timestamp);
