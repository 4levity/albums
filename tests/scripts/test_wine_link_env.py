"""Tests for docker/wine_link_env.sh (the wine jobs' baked-in environment guard)."""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "docker" / "wine_link_env.sh"


def run_guard(cwd: Path, wine_env: Path) -> subprocess.CompletedProcess[str]:
    sh = shutil.which("sh")
    assert sh is not None
    return subprocess.run(
        [sh, str(SCRIPT), str(wine_env)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def make_checkout(tmp_path: Path) -> Path:
    """A checkout stand-in: a cwd holding the wine script the fingerprint covers."""
    wine_script = tmp_path / "scripts" / "wine_setup.py"
    wine_script.parent.mkdir(parents=True)
    wine_script.write_text("# dummy wine script\n")
    return tmp_path


def fingerprint_for(checkout: Path) -> str:
    digest = hashlib.sha256((checkout / "scripts" / "wine_setup.py").read_bytes()).hexdigest()
    return f"{digest}  scripts/wine_setup.py"


@pytest.mark.skipif(shutil.which("sh") is None, reason="requires a POSIX shell")
class TestGuard:
    def test_reuses_wine_env_already_in_checkout(self, tmp_path):
        checkout = make_checkout(tmp_path)
        (checkout / ".cache" / "wine").mkdir(parents=True)
        result = run_guard(checkout, tmp_path / "env")
        assert result.returncode == 0
        assert "wine environment already in checkout; reusing it" in result.stdout
        assert not (checkout / ".cache" / "wine").is_symlink()

    def test_warns_when_env_missing(self, tmp_path):
        checkout = make_checkout(tmp_path)
        result = run_guard(checkout, tmp_path / "env")
        assert result.returncode == 0
        assert "::warning::no wine environment at" in result.stdout
        assert "building a fresh wine environment" in result.stdout
        assert not (checkout / ".cache").exists()

    def test_warns_when_fingerprint_stale(self, tmp_path):
        checkout = make_checkout(tmp_path)
        wine_env = tmp_path / "env"
        wine_env.mkdir()
        (wine_env / "fingerprint").write_text("0" * 64 + "  scripts/wine_setup.py\n")
        result = run_guard(checkout, wine_env)
        assert result.returncode == 0
        assert "does not match the wine scripts" in result.stdout
        assert "scripts/wine_setup.py: FAILED" in result.stdout
        assert "building a fresh wine environment" in result.stdout
        assert not (checkout / ".cache" / "wine").exists()

    def test_warns_when_env_locked(self, tmp_path):
        checkout = make_checkout(tmp_path)
        wine_env = tmp_path / "env"
        (wine_env / "prefix").mkdir(parents=True)
        (wine_env / "fingerprint").write_text(fingerprint_for(checkout) + "\n")
        (wine_env / "prefix" / ".lock").touch()
        result = run_guard(checkout, wine_env)
        assert result.returncode == 0
        assert "is locked" in result.stdout
        assert "building a fresh wine environment" in result.stdout
        assert not (checkout / ".cache" / "wine").exists()

    def test_links_env_when_guards_pass(self, tmp_path):
        checkout = make_checkout(tmp_path)
        wine_env = tmp_path / "env"
        wine_env.mkdir()
        (wine_env / "fingerprint").write_text(fingerprint_for(checkout) + "\n")
        result = run_guard(checkout, wine_env)
        assert result.returncode == 0
        assert "using baked-in wine environment" in result.stdout
        link = checkout / ".cache" / "wine"
        assert link.is_symlink()
        assert os.path.realpath(link) == os.path.realpath(wine_env)
