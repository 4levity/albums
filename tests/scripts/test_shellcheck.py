import hashlib
import io
import os
import sys
import tarfile

from scripts import shellcheck


def make_release_tarball(content: bytes = b"fake binary") -> tuple[bytes, str]:
    """Build a release tarball like the GitHub asset and return (data, sha256)."""
    member = tarfile.TarInfo(f"shellcheck-v{shellcheck.VERSION}/shellcheck")
    member.size = len(content)
    member.mode = 0o755
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:xz") as tar:
        tar.addfile(member, io.BytesIO(content))
    data = buffer.getvalue()
    return data, hashlib.sha256(data).hexdigest()


class TestMain:
    def test_linux_execs_cached_binary(self, monkeypatch, tmp_path):
        binary = tmp_path / "shellcheck"
        binary.write_text("#!/bin/sh\n")
        monkeypatch.setattr(sys, "argv", ["shellcheck.py", "--version"])
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(shellcheck, "cached_binary", lambda: binary)

        def no_download(*args, **kwargs):
            raise AssertionError("expected the cached binary, not a download")

        monkeypatch.setattr("urllib.request.urlopen", no_download)
        calls = []
        monkeypatch.setattr(os, "execv", lambda path, argv: calls.append((path, argv)))
        shellcheck.main()
        assert calls == [(binary, (str(binary), "--version"))]

    def test_darwin_execs_shellcheck_from_path(self, monkeypatch, tmp_path):
        shell = tmp_path / "shellcheck"
        shell.write_text("#!/bin/sh\n")
        monkeypatch.setattr(sys, "argv", ["shellcheck.py", "--version"])
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(shellcheck.shutil, "which", lambda name: str(shell))
        calls = []
        monkeypatch.setattr(os, "execv", lambda path, argv: calls.append((path, argv)))
        shellcheck.main()
        assert calls == [(str(shell), (str(shell), "--version"))]


class TestFetchLinux:
    def test_downloads_verifies_and_extracts(self, monkeypatch, tmp_path):
        data, sha = make_release_tarball()
        binary = tmp_path / f"shellcheck-v{shellcheck.VERSION}" / "shellcheck"
        monkeypatch.setattr(shellcheck, "cached_binary", lambda: binary)
        monkeypatch.setattr(shellcheck, "ASSET_SHA256", {"x86_64": sha})
        monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout: io.BytesIO(data))
        assert shellcheck.fetch_linux("x86_64") == binary
        assert binary.read_bytes() == b"fake binary"
        assert os.access(binary, os.X_OK)
