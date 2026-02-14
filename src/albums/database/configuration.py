import json
import sqlite3
from dataclasses import dataclass
from typing import List, Mapping, Union


@dataclass
class CheckConfiguration:
    enabled: bool
    settings: Mapping[str, Union[str, int, bool, List[str]]]


@dataclass
class Configuration:
    settings: Mapping[str, str]
    checks: Mapping[str, CheckConfiguration]


def load(db: sqlite3.Connection) -> Configuration:
    settings: dict[str, str] = dict((k, v) for k, v in db.execute("SELECT name, value FROM setting;"))
    checks: Mapping[str, CheckConfiguration] = {}
    for check_name, enabled in db.execute("SELECT check_name, enabled FROM checks;"):
        check_settings: dict[str, Union[str, int, bool, List[str]]] = dict(
            (k, json.loads(value_json))
            for k, value_json in db.execute("SELECT name, value_json FROM check_setting WHERE check_name = ?;", (check_name,))
        )
        checks[check_name] = CheckConfiguration(enabled, check_settings)
    return Configuration(settings, checks)


def save(db: sqlite3.Connection, configuration: Configuration):
    with db:
        for k, v in configuration.settings.items():
            db.execute("INSERT INTO setting(name, value) VALUES(?, ?) ON CONFLICT(name) DO UPDATE SET value = excluded.value;", (k, v))
        valid_keys = list(configuration.settings.keys())
        db.execute(f"DELETE FROM setting WHERE name NOT IN ({', '.join(['?'] * len(valid_keys))})", valid_keys)
        for check_name, check_configuration in configuration.checks.items():
            db.execute(
                "INSERT INTO checks(check_name, enabled) VALUES(?, ?) ON CONFLICT(check_name) DO UPDATE SET enabled = excluded.enabled;",
                (check_name, check_configuration.enabled),
            )
        valid_keys = list(configuration.checks.keys())
        db.execute(f"DELETE FROM checks WHERE check_name NOT IN ({', '.join(['?'] * len(valid_keys))})", valid_keys)
        for check_name, check_configuration in configuration.checks.items():
            for name, value in check_configuration.settings.items():
                db.execute(
                    "INSERT INTO check_setting(check_name, name, value_json) VALUES(?, ?, ?) ON CONFLICT(check_name, name) DO UPDATE SET value_json = excluded.value_json;",
                    (check_name, name, json.dumps(value)),
                )
            valid_keys = list(check_configuration.settings.keys())
            if len(valid_keys):
                db.execute(
                    f"DELETE FROM check_setting WHERE check_name = ? and name NOT IN ({', '.join(['?'] * len(valid_keys))});",
                    [check_name] + valid_keys,
                )
            else:
                db.execute("DELETE FROM check_setting WHERE check_name = ?;", (check_name,))
        db.commit()
