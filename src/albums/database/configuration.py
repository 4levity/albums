import json
import logging
import sqlite3

from ..types import Configuration

logger = logging.getLogger(__name__)


def load(db: sqlite3.Connection) -> Configuration:
    settings = ((k, json.loads(v)) for k, v in db.execute("SELECT name, value_json FROM setting;"))
    (config, ignored_values) = Configuration.from_values(settings)
    if ignored_values:
        save(db, config)  # showed warnings, now save valid config
    return config


def save(db: sqlite3.Connection, configuration: Configuration):
    settings = configuration.to_values()
    with db:
        for k, v in settings.items():
            db.execute(
                "INSERT INTO setting(name, value_json) VALUES(?, ?) ON CONFLICT(name) DO UPDATE SET value_json = excluded.value_json;",
                (k, json.dumps(v)),
            )
        valid_keys = list(settings.keys())
        db.execute(f"DELETE FROM setting WHERE name NOT IN ({', '.join(['?'] * len(valid_keys))})", valid_keys)
        db.commit()
