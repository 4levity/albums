import os

from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.path.check_duplicate_folder_name import CheckDuplicateFolderName
from albums.database import MEMORY, db_open
from albums.entities import Album, LibraryFolder, Track


def make_check(folders: list[tuple[str, str]]) -> tuple[Context, CheckDuplicateFolderName]:
    """Build the check over an in-memory database holding the given (parent_path, name) folders.

    The check reads the table in its constructor, so the session is closed afterwards: ``check()``
    itself must not need it (it never touches the file system).
    """
    ctx = Context()
    ctx.db = db_open(MEMORY)
    with Session(ctx.db) as session:
        for parent_path, name in folders:
            session.add(LibraryFolder(parent_path=parent_path, name=name, name_cf=str.casefold(name)))
        session.flush()
        check = CheckDuplicateFolderName(ctx, session=session)
    return (ctx, check)


def album(path: str) -> Album:
    return Album(path=path, tracks=[Track(filename="1.flac")])


class TestCheckDuplicateFolderName:
    def test_pass_with_empty_table(self):
        (ctx, check) = make_check([])
        try:
            assert check.check(album(f"Artist{os.sep}Album{os.sep}")) is None
        finally:
            ctx.db.dispose()

    def test_pass_without_case_conflicts(self):
        (ctx, check) = make_check([("Artist" + os.sep, "Album"), ("Artist" + os.sep, "Other")])
        try:
            assert check.check(album(f"Artist{os.sep}Album{os.sep}")) is None
        finally:
            ctx.db.dispose()

    def test_pass_when_names_differ_more_than_case(self):
        (ctx, check) = make_check([("Artist" + os.sep, "Album"), ("Artist" + os.sep, "Album 2")])
        try:
            assert check.check(album(f"Artist{os.sep}Album{os.sep}")) is None
        finally:
            ctx.db.dispose()

    def test_pass_when_case_variants_are_in_different_parents(self):
        (ctx, check) = make_check([("a" + os.sep, "Album"), ("b" + os.sep, "album")])
        try:
            assert check.check(album(f"a{os.sep}Album{os.sep}")) is None
        finally:
            ctx.db.dispose()

    def test_fail_with_case_variant_sibling_folder(self):
        (ctx, check) = make_check([("Artist" + os.sep, "Album"), ("Artist" + os.sep, "album")])
        try:
            result = check.check(album(f"Artist{os.sep}Album{os.sep}"))
            assert result is not None
            assert result.message == f'duplicate folder names: "Artist{os.sep}Album" and "Artist{os.sep}album" differ only in case'
            assert result.fixer is None
        finally:
            ctx.db.dispose()

    def test_fail_with_case_variant_sibling_album(self):
        (ctx, check) = make_check([("Artist" + os.sep, "Album"), ("Artist" + os.sep, "album")])
        try:
            left = album(f"Artist{os.sep}Album{os.sep}")
            right = album(f"Artist{os.sep}album{os.sep}")
            left_result = check.check(left)
            right_result = check.check(right)
            assert left_result is not None
            assert "Artist" + os.sep + "Album" in left_result.message
            assert "Artist" + os.sep + "album" in left_result.message
            assert right_result is not None
            assert "Artist" + os.sep + "album" in right_result.message
            assert "Artist" + os.sep + "Album" in right_result.message
        finally:
            ctx.db.dispose()

    def test_fail_with_case_variant_ancestor_folder(self):
        (ctx, check) = make_check([("Genre" + os.sep, "Artist"), ("Genre" + os.sep, "artist")])
        try:
            result = check.check(album(f"Genre{os.sep}Artist{os.sep}Album{os.sep}"))
            assert result is not None
            assert result.message == f'duplicate folder names: "Genre{os.sep}Artist" and "Genre{os.sep}artist" differ only in case'
        finally:
            ctx.db.dispose()

    def test_fail_with_case_variant_top_level_folder(self):
        (ctx, check) = make_check([("", "Artist"), ("", "artist")])
        try:
            result = check.check(album(f"Artist{os.sep}Album{os.sep}"))
            assert result is not None
            assert result.message == 'duplicate folder names: "Artist" and "artist" differ only in case'
        finally:
            ctx.db.dispose()

    def test_fail_with_unicode_casefold_variants(self):
        # capital sharp s (ß) casefolds to "strasse", like "Strasse"
        (ctx, check) = make_check([("Artist" + os.sep, "Strasse"), ("Artist" + os.sep, "Straße")])
        try:
            result = check.check(album(f"Artist{os.sep}Straße{os.sep}"))
            assert result is not None
            assert result.message == f'duplicate folder names: "Artist{os.sep}Straße" and "Artist{os.sep}Strasse" differ only in case'
        finally:
            ctx.db.dispose()

    def test_fail_with_three_way_conflict(self):
        # ẞ (capital sharp s) also casefolds to "ss", like ß and "SS"
        (ctx, check) = make_check([("Artist" + os.sep, "ß"), ("Artist" + os.sep, "ẞ"), ("Artist" + os.sep, "SS")])
        try:
            result = check.check(album(f"Artist{os.sep}ß{os.sep}"))
            assert result is not None
            assert result.message == f'duplicate folder names: "Artist{os.sep}ß" and "Artist{os.sep}SS", "Artist{os.sep}ẞ" differ only in case'
        finally:
            ctx.db.dispose()
