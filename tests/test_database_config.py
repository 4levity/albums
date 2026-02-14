import contextlib

from albums.database import connection
from albums.database.configuration import CheckConfiguration, Configuration, load, save


class TestDatabaseConfig:
    def test_database_config_load_empty(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            config = load(db)
            assert len(config.settings) == 0
            assert len(config.checks) == 0

    def test_database_config_save_load(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            config = Configuration(
                {"foo": "FOO"}, {"my_check": CheckConfiguration(True, {"string": "hello", "number": 1, "boolean": True, "list": ["a", "b"]})}
            )

            save(db, config)
            loaded = load(db)

            assert len(loaded.settings) == 1
            assert loaded.settings["foo"] == "FOO"
            assert len(loaded.checks) == 1
            check = loaded.checks["my_check"]
            assert check.enabled
            assert len(check.settings) == 4
            assert check.settings["string"] == "hello"
            assert check.settings["number"] == 1
            assert check.settings["boolean"]
            assert check.settings["list"] == ["a", "b"]

    def test_database_config_save_overwrite(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            save(db, Configuration({"foo": "FOO"}, {"my_check": CheckConfiguration(True, {"bar": "BAR"})}))
            loaded = load(db)
            assert loaded.settings["foo"] == "FOO"
            assert loaded.checks["my_check"].enabled
            assert loaded.checks["my_check"].settings["bar"] == "BAR"

            save(db, Configuration({"foo": "XFOO"}, {"my_check": CheckConfiguration(False, {"bar": "XBAR"})}))
            loaded = load(db)
            assert loaded.settings["foo"] == "XFOO"
            assert not loaded.checks["my_check"].enabled
            assert loaded.checks["my_check"].settings["bar"] == "XBAR"

    def test_database_config_save_remove(self):
        with contextlib.closing(connection.open(connection.MEMORY)) as db:
            save(
                db,
                Configuration(
                    {"foo": "FOO", "old": "OLD"},
                    {
                        "my_check": CheckConfiguration(True, {"bar": "BAR", "old_setting": "Old"}),
                        "old_check": CheckConfiguration(True, {"bar": "BAR"}),
                    },
                ),
            )
            loaded = load(db)
            assert loaded.settings["old"] == "OLD"
            assert loaded.checks["old_check"].enabled
            assert loaded.checks["my_check"].settings["old_setting"] == "Old"

            save(db, Configuration({"foo": "FOO"}, {"my_check": CheckConfiguration(True, {"bar": "BAR"})}))
            loaded = load(db)

            assert loaded.settings["foo"] == "FOO"
            assert "old" not in loaded.settings
            assert "old_check" not in loaded.checks
            assert loaded.checks["my_check"].settings["bar"] == "BAR"
            assert "old_setting" not in loaded.checks["my_check"].settings
