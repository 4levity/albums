"""Database schema migrations loaded from individual SQL files."""

import logging
from pathlib import Path
from typing import Final

from .migrate import migrate

logger: Final = logging.getLogger(__name__)


def get_init_schema() -> str:
    """Get the initial schema SQL (need to run migrations)"""
    with (Path(__file__).parent / "01_init.sql").open("r") as f:
        return f.read()


__all__ = ["get_init_schema", "migrate"]
