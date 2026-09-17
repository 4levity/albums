import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from albums.app import Context
from albums.database import MEMORY, db_open
from albums.entities import Album, LibraryFolder, Track
from albums.library.scanner import run_scan, sync_library_folders

from ..fixtures.create_library import create_library


def context(db, library: Path) -> Context:
    ctx = Context()
    ctx.db = db
    ctx.config.library = library
    return ctx


def folder_rows(session: Session) -> set[tuple[str, str, str]]:
    return {(p, n, cf) for (p, n, cf) in session.execute(select(LibraryFolder.parent_path, LibraryFolder.name, LibraryFolder.name_cf)).tuples()}


class TestSyncLibraryFolders:
    def test_first_sync_populates_table(self):
        db = db_open(MEMORY)
        try:
            with Session(db) as session:
                # as in a real walk, every folder's ancestors are walked too
                walked = {
                    ".",
                    "a" + os.sep,
                    "a" + os.sep + "b" + os.sep,
                    "genre" + os.sep,
                    "genre" + os.sep + "g" + os.sep,
                    "genre" + os.sep + "g" + os.sep + "Artist" + os.sep,
                    f"genre{os.sep}g{os.sep}Artist{os.sep}Album{os.sep}",
                }
                assert sync_library_folders(session, walked) is True
                assert folder_rows(session) == {
                    ("", "a", "a"),
                    ("a" + os.sep, "b", "b"),
                    ("", "genre", "genre"),
                    ("genre" + os.sep, "g", "g"),
                    (f"genre{os.sep}g{os.sep}", "Artist", "artist"),
                    (f"genre{os.sep}g{os.sep}Artist{os.sep}", "Album", "album"),
                }
        finally:
            db.dispose()

    def test_sync_same_folders_reports_no_change(self):
        db = db_open(MEMORY)
        try:
            walked = {"a" + os.sep, "b" + os.sep}
            with Session(db) as session:
                assert sync_library_folders(session, walked) is True
                assert sync_library_folders(session, walked) is False
        finally:
            db.dispose()

    def test_sync_detects_added_and_removed_folders(self):
        db = db_open(MEMORY)
        try:
            with Session(db) as session:
                assert sync_library_folders(session, {"a" + os.sep, "b" + os.sep}) is True
                assert sync_library_folders(session, {"a" + os.sep, "a" + os.sep + "c" + os.sep}) is True
                assert folder_rows(session) == {("", "a", "a"), ("a" + os.sep, "c", "c")}
        finally:
            db.dispose()

    def test_sync_stores_case_variant_names_distinctly(self):
        # in-memory data only (no such folders are created on disk): sibling folders that differ
        # only in case must be kept as separate rows sharing a casefold
        db = db_open(MEMORY)
        try:
            with Session(db) as session:
                walked = {
                    "Artist" + os.sep,
                    "Artist" + os.sep + "Album" + os.sep,
                    "Artist" + os.sep + "album" + os.sep,
                }
                assert sync_library_folders(session, walked) is True
                assert folder_rows(session) == {
                    ("", "Artist", "artist"),
                    ("Artist" + os.sep, "Album", "album"),
                    ("Artist" + os.sep, "album", "album"),
                }
        finally:
            db.dispose()

    def test_sync_stores_unicode_casefolds(self):
        db = db_open(MEMORY)
        try:
            with Session(db) as session:
                walked = {
                    "Artist" + os.sep + "ß" + os.sep,
                    "Artist" + os.sep + "SS" + os.sep,
                    "Artist" + os.sep + "Strasse" + os.sep,
                }
                assert sync_library_folders(session, walked) is True
                assert folder_rows(session) == {
                    ("Artist" + os.sep, "ß", "ss"),
                    ("Artist" + os.sep, "SS", "ss"),
                    ("Artist" + os.sep, "Strasse", "strasse"),
                }
        finally:
            db.dispose()


class TestScanLibraryFolders:
    def test_full_scan_records_all_folders(self):
        db = db_open(MEMORY)
        try:
            albums = [
                Album(path=f"genre{os.sep}g{os.sep}Artist{os.sep}Album1{os.sep}", tracks=[Track(filename="1.flac")]),
                Album(path=f"genre{os.sep}g{os.sep}Artist{os.sep}Album2{os.sep}", tracks=[Track(filename="1.mp3")]),
            ]
            library = create_library("test_scan_library_folders", albums)
            (library / "genre" / "g" / "Artist" / "notes").mkdir()  # non-album folder, must be recorded too
            (library / "genre" / "h").mkdir()
            run_scan(context(db, library))
            with Session(db) as session:
                assert folder_rows(session) == {
                    ("", "genre", "genre"),
                    ("genre" + os.sep, "g", "g"),
                    ("genre" + os.sep, "h", "h"),
                    (f"genre{os.sep}g{os.sep}", "Artist", "artist"),
                    (f"genre{os.sep}g{os.sep}Artist{os.sep}", "Album1", "album1"),
                    (f"genre{os.sep}g{os.sep}Artist{os.sep}", "Album2", "album2"),
                    (f"genre{os.sep}g{os.sep}Artist{os.sep}", "notes", "notes"),
                }
        finally:
            db.dispose()

    def test_rescan_without_folder_changes_reports_no_change(self):
        db = db_open(MEMORY)
        try:
            albums = [Album(path="album" + os.sep, tracks=[Track(filename="1.flac")])]
            library = create_library("test_scan_library_folders_unchanged", albums)
            ctx = context(db, library)
            run_scan(ctx)
            (albums_total, changed) = run_scan(ctx)
            assert changed is False
            assert albums_total == 1
        finally:
            db.dispose()
