"""Shared pytest fixtures for the test suite."""

from typing import Any

import pytest
from sqlalchemy import Engine

from albums.database import connection


@pytest.fixture(autouse=True)
def dispose_engines(monkeypatch):
    """Dispose of every database engine created during a test.

    Tests (and in-process CLI invocations) open engines via ``db_open()`` and
    usually don't dispose of them. SQLAlchemy keeps in-memory SQLite
    connections open until the engine is disposed or garbage-collected, and
    the timing of that collection (which shifts when running under coverage)
    can surface ResourceWarnings for unclosed connections. Disposing
    deterministically at test end removes that.
    """
    engines: list[Engine] = []
    real_create_engine = connection.create_engine

    def tracking_create_engine(*args: Any, **kwargs: Any) -> Engine:
        engine = real_create_engine(*args, **kwargs)
        engines.append(engine)
        return engine

    monkeypatch.setattr(connection, "create_engine", tracking_create_engine)
    yield
    for engine in engines:
        engine.dispose()
