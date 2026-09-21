import sys

import pytest

from scripts import fileversion


class TestFileVersion:
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
        assert fileversion.file_version(release) == file_version


class TestMain:
    def test_main_prints_file_version(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["fileversion.py", "1.2.3.post4+g1234abcd"])
        assert fileversion.main() == 0
        assert capsys.readouterr().out == "1.2.3.4\n"

    def test_main_without_version_fails(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["fileversion.py"])
        assert fileversion.main() == 1
        assert "usage" in capsys.readouterr().err
