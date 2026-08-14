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
from albums.database.selector import Comparator, Match, collections_by_name, load_album_entities

__all__ = [
    "Base",
    "Comparator",
    "IntEnumAsInt",
    "LoadIssuesAsJson",
    "LoadIssuesType",
    "Match",
    "MEMORY",
    "NO_DEFAULT_VALUE_LIST_STR",
    "SafeStringEnum",
    "SerializableValueAsJson",
    "collections_by_name",
    "db_open",
    "get_init_schema",
    "load_album_entities",
    "migrate",
]
