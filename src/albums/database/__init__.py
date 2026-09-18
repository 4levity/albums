"""Database package providing connection, configuration, schema management and query helpers."""

from albums.database.connection import MEMORY, db_open
from albums.database.migrations import get_init_schema, migrate
from albums.database.orm import (
    NO_DEFAULT_VALUE_LIST_STR,
    Base,
    BasicFieldsAsJson,
    IntEnumAsInt,
    LoadIssuesAsJson,
    SafeStringEnum,
    SerializableValueAsJson,
)
from albums.picture import LoadIssuesType

__all__ = [
    "Base",
    "BasicFieldsAsJson",
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
