-- v9: Add setting table for storing application settings

CREATE TABLE setting (
    name TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
) WITHOUT ROWID;
