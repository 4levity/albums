import os
from pathlib import Path

import pytest

from albums.library.folder import walk_paths


class TestWalkPaths:
    def test_empty_root(self, tmp_path: Path):
        assert list(walk_paths(tmp_path)) == ["."]

    def test_missing_root(self, tmp_path: Path):
        assert list(walk_paths(tmp_path / "nope")) == ["."]

    def test_nested_folders(self, tmp_path: Path):
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        sep = os.sep
        assert sorted(walk_paths(tmp_path)) == [".", f"a{sep}", f"a{sep}b{sep}", f"a{sep}b{sep}c{sep}"]

    def test_hidden_folders_skipped(self, tmp_path: Path):
        (tmp_path / ".hidden" / "inner").mkdir(parents=True)
        (tmp_path / "a" / ".deep" / "b").mkdir(parents=True)
        sep = os.sep
        assert sorted(walk_paths(tmp_path)) == [".", f"a{sep}"]

    def test_root_name_may_be_hidden(self, tmp_path: Path):
        root = tmp_path / ".music"
        (root / "a").mkdir(parents=True)
        assert sorted(walk_paths(root)) == [".", f"a{os.sep}"]

    def test_symlinked_folder_followed(self, tmp_path: Path):
        (tmp_path / "real" / "album").mkdir(parents=True)
        try:
            (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
        except OSError:
            pytest.skip("symlinks not supported here")
        sep = os.sep
        assert sorted(walk_paths(tmp_path)) == [".", f"link{sep}", f"link{sep}album{sep}", f"real{sep}", f"real{sep}album{sep}"]
