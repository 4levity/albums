import sys

from scripts import version


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
