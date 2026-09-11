import sys

import pytest

from scripts import version


class TestGetFileVersion:
    @pytest.mark.parametrize(
        ("release", "file_version"),
        [
            ("0.9.30", "0.9.30.0"),
            ("0.9.30.post5+g1234abcd", "0.9.30.5"),
            ("0.9.30.post5+g1234abcd.d20260901", "0.9.30.5"),
            ("0.9.30.dev3", "0.9.30.3"),
        ],
    )
    def test_file_version(self, release, file_version):
        assert version.get_file_version(release) == file_version


class TestMain:
    def test_fileversion_prints_file_version(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["version.py", "fileversion"])
        monkeypatch.setattr(version, "get_albums_version", lambda: "1.2.3.post4+g1234abcd")
        assert version.main() == 0
        assert capsys.readouterr().out == "1.2.3.4\n"

    def test_write_writes_version_file(self, monkeypatch, tmp_path):
        (tmp_path / "src" / "albums").mkdir(parents=True)
        monkeypatch.setattr(sys, "argv", ["version.py", "write"])
        monkeypatch.setattr(version, "get_albums_version", lambda: "1.2.3")
        monkeypatch.chdir(tmp_path)
        assert version.main() == 0
        assert "1.2.3" in (tmp_path / "src" / "albums" / "_version.py").read_text()
