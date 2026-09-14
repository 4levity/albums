"""Shared helpers for the wine-based Windows build scripts (wine_setup, wine_build)."""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, NoReturn, cast

ROOT = Path(__file__).resolve().parents[1]
WINE_ROOT = ROOT / ".cache" / "wine"
BUILD_PREFIX = WINE_ROOT / "prefix"  # prefix for wine_setup, wine_build, wine_pytest
BIN = WINE_ROOT / "bin"
UV_CACHE = WINE_ROOT / "uv-cache"
VENV = WINE_ROOT / "venv"  # wine venv for `uv sync` (used by wine_build.py)
ISCC = BUILD_PREFIX / "drive_c" / "InnoSetup7" / "ISCC.exe"

WINE_MIN_VERSION = (11, 0)


def fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """Run a subprocess, printing the command to the console as it is executed."""
    print(f"running: {' '.join(cmd)}")
    # cast: **kwargs is Any, so pyright cannot infer subprocess.run's return type
    return cast("subprocess.CompletedProcess[Any]", subprocess.run(cmd, **kwargs))


def find_wine() -> str:
    wine = shutil.which("wine")
    if wine is None:
        fail(f"wine not found on PATH; install wine {WINE_MIN_VERSION[0]}.{WINE_MIN_VERSION[1]} or newer")
    output = run([wine, "--version"], capture_output=True, text=True).stdout.strip()
    match = re.search(r"(\d+)\.(\d+)", output)
    if match is None or (int(match.group(1)), int(match.group(2))) < WINE_MIN_VERSION:
        fail(f"wine {output} is too old; {WINE_MIN_VERSION[0]}.{WINE_MIN_VERSION[1]} or newer is required")
    return wine


def wine_env(prefix: Path) -> dict[str, str]:
    """Environment for wine commands: the given prefix, quiet, uv cache on the host filesystem."""
    env = {
        **os.environ,
        "WINEPREFIX": str(prefix),
        "WINEDEBUG": "-all",
        "UV_CACHE_DIR": str(UV_CACHE),
        "UV_PROJECT_ENVIRONMENT": str(VENV),
        # do not prompt to install wine-mono (not needed)
        "WINEDLLOVERRIDES": 'mscoree=""',
    }
    # drop the host venv: wine's uv would try to inspect it with Windows paths
    env.pop("VIRTUAL_ENV", None)
    return env


def display_wine_cmd(wine: str) -> list[str]:
    """Wine command for steps that need a display; xvfb-run when none is set."""
    if os.environ.get("DISPLAY"):
        return [wine]
    xvfb = shutil.which("xvfb-run")
    if xvfb is None:
        fail("no display and xvfb-run not found; install xvfb (e.g. `sudo apt install xvfb`)")
    return [xvfb, "-a", wine]


def run_wine(cmd: list[str], args: list[str], prefix: Path, timeout: int = 600, check: bool = True) -> None:
    """Run a program under wine in the prefix, streaming its output."""
    try:
        run([*cmd, *args], env=wine_env(prefix), cwd=ROOT, check=check, timeout=timeout)
    except subprocess.CalledProcessError as e:
        fail(f"wine command failed (exit {e.returncode}): {' '.join(cmd + args)}")
    except subprocess.TimeoutExpired:
        fail(f"wine command timed out after {timeout}s: {' '.join(cmd + args)}")


def kill_wineserver(prefix: Path) -> None:
    """Stop a prefix's wineserver (flushes its registry to disk).

    Kill a prefix after using it: deleting a prefix while its server is running
    is unsafe (the server may recreate it), and `make clean` or `git clean`
    can delete the prefix at any time. No-op if the prefix does not exist, as
    running wineserver would create it.
    """
    if not prefix.is_dir():
        return
    run_wine(["wineserver"], ["-k"], check=False, prefix=prefix)


def wine_capture(cmd: list[str], args: list[str], prefix: Path, timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a program under wine in the prefix, capturing output; return the process."""
    try:
        return run([*cmd, *args], env=wine_env(prefix), cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=check)
    except subprocess.CalledProcessError as e:
        lines = (e.stdout or "").splitlines() + (e.stderr or "").splitlines()
        fail(f"wine command failed (exit {e.returncode}): {' '.join(cmd + args)}\n" + "\n".join(lines[-10:]))
    except subprocess.TimeoutExpired:
        fail(f"wine command timed out after {timeout}s: {' '.join(cmd + args)}")


def download(url: str, dest: Path, sha256: str) -> Path:
    """Download url to dest (skipped if already there), verifying the sha256 sum."""
    if dest.is_file():
        return dest
    print(f"downloading {dest.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=dest.parent, suffix=".part")
    tmp = Path(tmp_name)
    os.close(fd)
    try:
        with urllib.request.urlopen(url, timeout=300) as response, tmp.open("wb") as out:
            shutil.copyfileobj(response, out)
        actual = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if actual != sha256:
            fail(f"sha256 mismatch for {dest.name}: expected {sha256}, got {actual}")
        os.replace(tmp, dest)
    except OSError as e:
        fail(f"downloading {dest.name} failed: {e}")
    finally:
        tmp.unlink(missing_ok=True)
    return dest
