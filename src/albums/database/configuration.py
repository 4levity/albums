import json
import logging
import sqlite3
from typing import Any

from albums.checks.all import ALL_CHECK_NAMES, DEFAULT_CHECK_CONFIGS
from albums.config import DEFAULT_SETTINGS, CheckConfiguration, Configuration

logger = logging.getLogger(__name__)


def load(db: sqlite3.Connection) -> Configuration:
    config = Configuration({}, {})
    for name, value_json in db.execute("SELECT name, value_json FROM setting;"):
        [section, key] = name.split(".")
        value = json.loads(value_json)
        if section == "settings":
            if key in DEFAULT_SETTINGS:
                config.settings[key] = value
            else:
                logger.warning(f"ignoring unknown setting {key}={value}")
        else:
            if section in ALL_CHECK_NAMES:
                if section not in config.checks:
                    config.checks[section] = CheckConfiguration(False, {})
                if key == "enabled":
                    config.checks[section].enabled = value
                else:
                    if key in DEFAULT_CHECK_CONFIGS[section]:
                        config.checks[section].settings[key] = value
                    else:
                        logger.warning(f"ignoring unknown setting for {section} - {key}={value}")
            else:
                logger.warning(f"ignoring unknown section/check {section}")

    # fully populate all defaults
    for k in DEFAULT_SETTINGS.keys() - config.settings.keys():
        config.settings[k] = DEFAULT_SETTINGS[k]
    for c in ALL_CHECK_NAMES:
        if c not in config.checks:
            config.checks[c] = CheckConfiguration(
                DEFAULT_CHECK_CONFIGS[c]["enabled"], dict((k, v) for k, v in DEFAULT_CHECK_CONFIGS[c].items() if k != "enabled")
            )
        else:
            for k in DEFAULT_CHECK_CONFIGS[c].keys() - config.checks[c].settings.keys():
                config.checks[c].settings[k] = DEFAULT_CHECK_CONFIGS[c][k]
    return config


def save(db: sqlite3.Connection, configuration: Configuration):
    unknown_settings = configuration.settings.keys() - DEFAULT_SETTINGS
    if unknown_settings:
        raise ValueError(f"unknown settings: {', '.join(unknown_settings)}")
    settings: dict[str, Any] = dict((f"settings.{k}", v) for k, v in configuration.settings.items())
    for check_name, check_configuration in configuration.checks.items():
        if check_name not in ALL_CHECK_NAMES:
            raise ValueError(f"invalid check name: {check_name}")
        settings[f"{check_name}.enabled"] = check_configuration.enabled
        unknown_settings = check_configuration.settings.keys() - set(DEFAULT_CHECK_CONFIGS[check_name].keys())
        if unknown_settings:
            raise ValueError(f"unknown check {check_name} settings: {', '.join(unknown_settings)}")
        settings.update(dict((f"{check_name}.{k}", v) for k, v in check_configuration.settings.items()))
    for k, v in settings.items():
        if not _valid_value(v):  # TODO check type against default value
            raise ValueError(f"invalid type of value for setting {k}: {str(v)}")
    with db:
        for k, v in settings.items():
            db.execute(
                "INSERT INTO setting(name, value_json) VALUES(?, ?) ON CONFLICT(name) DO UPDATE SET value_json = excluded.value_json;",
                (k, json.dumps(v)),
            )
        valid_keys = list(settings.keys())
        db.execute(f"DELETE FROM setting WHERE name NOT IN ({', '.join(['?'] * len(valid_keys))})", valid_keys)
        db.commit()


def _valid_value(value: Any) -> bool:
    return value is not None and (
        isinstance(value, str)
        or isinstance(value, int)
        or isinstance(value, bool)
        or (isinstance(value, list) and all(isinstance(v, str) for v in value))  # pyright: ignore[reportUnknownVariableType]
    )
