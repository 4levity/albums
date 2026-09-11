"""Fetch and run a pinned shellcheck release.

On Linux, downloads the pinned release into the project's (gitignored)
`.cache/shellcheck/` folder, so no shellcheck install is needed. On other
platforms, runs `shellcheck` from PATH; install it there (see
docs/developing.md).

Usage: python scripts/shellcheck.py [shellcheck arguments]
"""

import hashlib
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import NoReturn

# Pinned release and the sha256 of its Linux assets
# (shellcheck-v{VERSION}.linux.{arch}.tar.xz from the GitHub release).
VERSION = "0.11.0"
ASSET_SHA256 = {
    "x86_64": "8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198",
    "aarch64": "12b331c1d2db6b9eb13cfca64306b1b157a86eb69db83023e261eaa7e7c14588",
}
# uname -m value -> release asset arch
MACHINE_ARCH = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
}


def fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def cached_binary() -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / ".cache" / "shellcheck" / f"shellcheck-v{VERSION}" / "shellcheck"


def fetch_linux(arch: str) -> Path:
    """Download the pinned release (if not already cached) and return the binary."""
    binary = cached_binary()
    if binary.is_file():
        return binary
    asset = f"shellcheck-v{VERSION}.linux.{arch}.tar.xz"
    url = f"https://github.com/koalaman/shellcheck/releases/download/v{VERSION}/{asset}"
    cache_dir = binary.parent.parent
    print(f"downloading shellcheck v{VERSION} ({arch}) to {cache_dir}", file=sys.stderr)
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache_dir) as tmp:
        tarball = Path(tmp) / asset
        with urllib.request.urlopen(url, timeout=60) as response, tarball.open("wb") as out:
            shutil.copyfileobj(response, out)
        actual = hashlib.sha256(tarball.read_bytes()).hexdigest()
        if actual != ASSET_SHA256[arch]:
            fail(f"sha256 mismatch for {asset}: expected {ASSET_SHA256[arch]}, got {actual}")
        with tarfile.open(tarball, mode="r:xz") as tar:
            tar.extractall(cache_dir, filter="data")
    os.chmod(binary, 0o755)
    return binary


def main() -> int:
    args = sys.argv[1:]
    if sys.platform == "linux":
        arch = MACHINE_ARCH.get(platform.machine().lower())
        if arch is None:
            fail(f"no shellcheck download for Linux {platform.machine()!r}; install it on PATH")
        binary = fetch_linux(arch)
    else:
        binary = shutil.which("shellcheck")
        if binary is None:
            fail("shellcheck is not on PATH; install it (e.g. brew install shellcheck) and re-run")
    os.execv(binary, (str(binary), *args))


if __name__ == "__main__":
    sys.exit(main())
