from pathlib import Path

import pytest

from scripts import render_iss, version

TEMPLATE = (Path(__file__).resolve().parents[2] / "scripts" / "albums.iss").read_text()


class TestRenderInstallerScript:
    def test_replaces_placeholder_versions(self):
        text = render_iss.render_installer_script(TEMPLATE, "0.9.31.post6+g53b1731cf", "0.9.31.6")
        lines = text.splitlines()
        assert "AppVersion=0.9.31.post6+g53b1731cf" in lines
        assert "AppVerName=albums 0.9.31.post6+g53b1731cf" in lines
        assert "VersionInfoVersion=0.9.31.6" in lines
        assert "OutputBaseFilename=albums_win_x86_64-0.9.31.6-setup" in lines

    def test_does_not_render_comment_lines(self):
        text = render_iss.render_installer_script(TEMPLATE, "1.2.3", "1.2.3.0")
        assert "The 0.0.0 version" in text

    def test_does_not_touch_versions_containing_the_placeholder(self):
        # the file version of 1.0.0 is 1.0.0.0, which contains 0.0.0
        text = render_iss.render_installer_script(TEMPLATE, "1.0.0", "1.0.0.0")
        lines = text.splitlines()
        assert "AppVersion=1.0.0" in lines
        assert "VersionInfoVersion=1.0.0.0" in lines
        assert "OutputBaseFilename=albums_win_x86_64-1.0.0.0-setup" in lines

    def test_unchanged_for_fallback_version(self):
        assert render_iss.render_installer_script(TEMPLATE, "0.0.0", "0.0.0.0") == TEMPLATE


class TestDisplayVersion:
    @pytest.mark.parametrize(
        ("version", "display"),
        [
            ("0.9.31", "0.9.31"),
            ("0.9.31.post9+gb924d3c4b.d20260911", "0.9.31.post9"),
            ("0.9.31.post9+gb924d3c4b.d20260911.dirty", "0.9.31.post9"),
            ("0.9.31.dev3+g1234abcd", "0.9.31.dev3"),
            ("0.0.0", "0.0.0"),
        ],
    )
    def test_display_version(self, version, display):
        assert render_iss.display_version(version) == display


class TestMain:
    def test_writes_rendered_script(self, monkeypatch, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "albums.iss").write_text(TEMPLATE)
        monkeypatch.setattr(version, "get_albums_version", lambda: "1.2.3.post4+g1234abcd")
        monkeypatch.chdir(tmp_path)
        assert render_iss.main() == 0
        lines = (tmp_path / "build" / "albums.iss").read_text().splitlines()
        assert "AppVersion=1.2.3.post4" in lines
        assert "AppVerName=albums 1.2.3.post4" in lines
        assert "VersionInfoVersion=1.2.3.4" in lines

    def test_fails_without_placeholder_versions(self, monkeypatch, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "albums.iss").write_text("AppVersion=1.2.3\n")
        monkeypatch.chdir(tmp_path)
        assert render_iss.main() == 1
