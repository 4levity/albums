"""Fetch and run a pinned actionlint release.

On Linux, downloads the pinned release into the project's (gitignored)
`.cache/actionlint/` folder, so no actionlint install is needed. On other
platforms, runs `actionlint` from PATH; install it there (see
docs/developing.md).

Usage: python scripts/actionlint.py [actionlint arguments]
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
# (actionlint_{VERSION}_linux_{arch}.tar.gz from the GitHub release).
VERSION = "1.7.9"
ASSET_SHA256 = {
    "amd64": "233b280d05e100837f4af1433c7b40a5dcb306e3aa68fb4f17f8a7f45a7df7b4",
    "arm64": "6b82a3b8c808bf1bcd39a95aced22fc1a026eef08ede410f81e274af8deadbbc",
}
# uname -m value -> release asset arch
MACHINE_ARCH = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
}


def fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def cached_binary() -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / ".cache" / "actionlint" / f"actionlint-{VERSION}" / "actionlint"


def fetch_linux(arch: str) -> Path:
    """Download the pinned release (if not already cached) and return the binary."""
    binary = cached_binary()
    if binary.is_file():
        return binary
    asset = f"actionlint_{VERSION}_linux_{arch}.tar.gz"
    url = f"https://github.com/rhysd/actionlint/releases/download/v{VERSION}/{asset}"
    cache_dir = binary.parent
    print(f"downloading actionlint v{VERSION} ({arch}) to {cache_dir}", file=sys.stderr)
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache_dir) as tmp:
        tarball = Path(tmp) / asset
        with urllib.request.urlopen(url, timeout=60) as response, tarball.open("wb") as out:
            shutil.copyfileobj(response, out)
        actual = hashlib.sha256(tarball.read_bytes()).hexdigest()
        if actual != ASSET_SHA256[arch]:
            fail(f"sha256 mismatch for {asset}: expected {ASSET_SHA256[arch]}, got {actual}")
        # the release tarball bundles docs and man pages too; take the binary only
        with tarfile.open(tarball, mode="r:gz") as tar:
            tar.extract("actionlint", cache_dir, filter="data")
    os.chmod(binary, 0o755)
    return binary


def main() -> int:
    args = sys.argv[1:]
    if sys.platform == "linux":
        arch = MACHINE_ARCH.get(platform.machine().lower())
        if arch is None:
            fail(f"no actionlint download for Linux {platform.machine().lower()!r}; install it on PATH")
        binary = fetch_linux(arch)
    else:
        binary = shutil.which("actionlint")
        if binary is None:
            fail("actionlint is not on PATH; install it (e.g. brew install actionlint) and re-run")
    os.execv(binary, (str(binary), *args))


if __name__ == "__main__":
    sys.exit(main())
