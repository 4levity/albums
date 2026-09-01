"""Database package providing connection, configuration, schema management and query helpers."""

from albums.database.connection import MEMORY, db_open
from albums.database.migrations import get_init_schema, migrate
from albums.database.orm import (
    NO_DEFAULT_VALUE_LIST_STR,
    Base,
    IntEnumAsInt,
    LoadIssuesAsJson,
    LoadIssuesType,
    SafeStringEnum,
    SerializableValueAsJson,
)

__all__ = [
    "Base",
    "IntEnumAsInt",
    "LoadIssuesAsJson",
    "LoadIssuesType",
    "MEMORY",
    "NO_DEFAULT_VALUE_LIST_STR",
    "SafeStringEnum",
    "SerializableValueAsJson",
    "db_open",
    "get_init_schema",
    "migrate",
]
