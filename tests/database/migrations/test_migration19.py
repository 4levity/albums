import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from albums.checks.all import ALL_CHECKS
from albums.database import MEMORY, db_open, migrate
from albums.database.migrations.migrate import _load_migrations


def _add_album_with_ignores(db, album_id: int, check_names: list[str]):
    with db.begin() as conn:
        conn.execute(text("INSERT INTO album (album_id, path) VALUES (:id, :path);"), {"id": album_id, "path": f"album{album_id}/"})
        for check_name in check_names:
            conn.execute(text("INSERT INTO album_ignore_check (album_id, check_name) VALUES (:id, :name);"), {"id": album_id, "name": check_name})


def _ignore_rows(db) -> list[tuple[int, str]]:
    with Session(db) as session:
        return sorted((row.album_id, row.check_name) for row in session.execute(text("SELECT album_id, check_name FROM album_ignore_check;")))


class TestMigration19RemoveRedundantIgnores:
    """Migration 19 removes ignored checks that are implicitly ignored because they depend on an ignored check."""

    def test_redundant_ignore_removed(self):
        """An ignored check whose dependency is also ignored for the same album is removed."""
        db = db_open(MEMORY, version=18)
        try:
            _add_album_with_ignores(db, 1, ["disc-in-track-number", "invalid-track-or-disc-number"])
            migrate(db, quiet=True, target_version=19)
            assert _ignore_rows(db) == [(1, "disc-in-track-number")]
        finally:
            db.dispose()

    def test_transitive_chain_removed(self):
        """Checks transitively depending on an ignored check are all removed, keeping only the root."""
        db = db_open(MEMORY, version=18)
        try:
            _add_album_with_ignores(db, 1, ["disc-in-track-number", "disc-numbering", "track-numbering", "zero-pad-numbers", "track-filename"])
            migrate(db, quiet=True, target_version=19)
            assert _ignore_rows(db) == [(1, "disc-in-track-number")]
        finally:
            db.dispose()

    def test_independent_ignores_kept(self):
        """Ignored checks that do not depend on each other are all kept."""
        db = db_open(MEMORY, version=18)
        try:
            _add_album_with_ignores(db, 1, ["disc-in-track-number", "album"])
            migrate(db, quiet=True, target_version=19)
            assert _ignore_rows(db) == [(1, "album"), (1, "disc-in-track-number")]
        finally:
            db.dispose()

    def test_ignores_are_per_album(self):
        """A check is only redundant if its dependency is ignored for the same album."""
        db = db_open(MEMORY, version=18)
        try:
            # album 1 ignores invalid-track-or-disc-number without ignoring its dependency: kept
            # album 2 ignores both: the dependent is redundant and removed
            _add_album_with_ignores(db, 1, ["invalid-track-or-disc-number"])
            _add_album_with_ignores(db, 2, ["disc-in-track-number", "invalid-track-or-disc-number"])
            migrate(db, quiet=True, target_version=19)
            assert _ignore_rows(db) == [(1, "invalid-track-or-disc-number"), (2, "disc-in-track-number")]
        finally:
            db.dispose()

    def test_noop_without_ignores(self):
        db = db_open(MEMORY, version=18)
        try:
            with db.begin() as conn:
                conn.execute(text("INSERT INTO album (path) VALUES ('foo/');"))
            migrate(db, quiet=True, target_version=19)
            assert _ignore_rows(db) == []
        finally:
            db.dispose()

    def test_rerun_is_idempotent(self):
        """Re-running migration 19 (e.g. after a crash before the version bump) must not remove anything extra."""
        db = db_open(MEMORY, version=18)
        try:
            _add_album_with_ignores(db, 1, ["disc-in-track-number", "invalid-track-or-disc-number", "track-filename"])
            migrate(db, quiet=True, target_version=19)

            # Simulate the migration being re-run after a crash: version still 18, script applied again
            with db.begin() as conn:
                conn.connection.executescript(_load_migrations()[19])

            assert _ignore_rows(db) == [(1, "disc-in-track-number")]
        finally:
            db.dispose()

    def test_migration_pairs_match_check_dependencies(self):
        """The dependency pairs hard-coded in the migration must match the checks' must_pass_checks, so the
        migration stays correct as the check graph evolves."""
        pairs_in_sql = {tuple(pair) for pair in re.findall(r"\(\s*'([^']+)'\s*,\s*'([^']+)'\s*\)", _load_migrations()[19])}
        pairs_in_code = {(check.name, dep) for check in ALL_CHECKS for dep in check.must_pass_checks}
        assert pairs_in_sql == pairs_in_code
