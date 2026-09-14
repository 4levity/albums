"""Create the wine environment for building the Windows installer on Linux.

Idempotent. Creates a wine prefix in the gitignored `.cache/wine/` folder and
installs into it: uv (which downloads the Windows Python the build uses) and
Inno Setup. Requires wine 11.0 or newer; on headless systems the Inno Setup
installer runs under xvfb-run, which needs the xvfb package.

Usage: python scripts/wine_setup.py
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
WINE_ROOT = ROOT / ".cache" / "wine"
PREFIX = WINE_ROOT / "prefix"
BIN = WINE_ROOT / "bin"
DOWNLOADS = WINE_ROOT / "downloads"
UV_CACHE = WINE_ROOT / "uv-cache"
VENV = WINE_ROOT / "venv"  # wine venv for `uv sync` (used by wine_build.py)

# Pinned releases and the sha256 of their release assets. Python is not
# pinned: uv picks the latest 3.12.x, as the Windows CI job does.
UV_VERSION = "0.9.26"
UV_SHA256 = "eb02fd95d8e0eed462b4a67ecdd320d865b38c560bffcda9a0b87ec944bdf036"  # uv-x86_64-pc-windows-msvc.zip
INNOSETUP_VERSION = "7.1.0"
INNOSETUP_SHA256 = "0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f"  # innosetup-7.1.0-x64.exe
PYTHON_VERSION = "3.12"
# deterministic Inno Setup install location, passed to its own installer via /DIR
INNO_DIR = r"C:\InnoSetup7"
INNO_LOG = "inno-setup-install.log"
ISCC = PREFIX / "drive_c" / "InnoSetup7" / "ISCC.exe"


def fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


WINE_MIN_VERSION = (11, 0)


def find_wine() -> str:
    wine = shutil.which("wine")
    if wine is None:
        fail(f"wine not found on PATH; install wine {WINE_MIN_VERSION[0]}.{WINE_MIN_VERSION[1]} or newer")
    output = subprocess.run([wine, "--version"], capture_output=True, text=True).stdout.strip()
    match = re.search(r"(\d+)\.(\d+)", output)
    if match is None or (int(match.group(1)), int(match.group(2))) < WINE_MIN_VERSION:
        fail(f"wine {output} is too old; {WINE_MIN_VERSION[0]}.{WINE_MIN_VERSION[1]} or newer is required")
    _wine = wine
    return wine


def display_wine_cmd(wine: str) -> list[str]:
    """Wine command for the Inno Setup installer, which needs a display even in silent mode."""
    if os.environ.get("DISPLAY"):
        return [wine]
    xvfb = shutil.which("xvfb-run")
    if xvfb is None:
        fail("no display and xvfb-run not found; install xvfb (e.g. `sudo apt install xvfb`)")
    return [xvfb, "-a", wine]


def wine_env() -> dict[str, str]:
    """Environment for wine commands: project prefix, quiet, uv cache on the host filesystem."""
    env = {
        **os.environ,
        "WINEPREFIX": str(PREFIX),
        "WINEDEBUG": "-all",
        "UV_CACHE_DIR": str(UV_CACHE),
        "UV_PROJECT_ENVIRONMENT": str(VENV),
        # do not prompt to install wine-mono (not needed)
        "WINEDLLOVERRIDES": 'mscoree=""',  # cspell: ignore WINEDLLOVERRIDES, mscoree
    }
    # drop the host venv: wine's uv would try to inspect it with Windows paths
    env.pop("VIRTUAL_ENV", None)
    return env


def run_wine(cmd: list[str], args: list[str], timeout: int = 600, check: bool = True) -> None:
    """Run a program under wine in the prefix, streaming its output."""
    try:
        subprocess.run([*cmd, *args], env=wine_env(), cwd=ROOT, check=check, timeout=timeout)
    except subprocess.CalledProcessError as e:
        fail(f"wine command failed (exit {e.returncode}): {' '.join(cmd + args)}")
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


def ensure_prefix(wine: str) -> None:
    if (PREFIX / "drive_c").is_dir():
        print("wine prefix exists")
        return
    print(f"creating wine prefix in {PREFIX.relative_to(ROOT)}")
    WINE_ROOT.mkdir(parents=True, exist_ok=True)
    # a fresh prefix's X support only initializes when wineboot runs on a display
    run_wine(display_wine_cmd(wine), ["wineboot", "--init"], timeout=300)
    if not (PREFIX / "drive_c").is_dir():
        fail(f"wineboot did not create {PREFIX.relative_to(ROOT)}/drive_c")


def ensure_uv() -> None:
    uv_exe = BIN / "uv.exe"
    if uv_exe.is_file():
        print(f"uv {UV_VERSION} (Windows) installed")
        return
    asset = "uv-x86_64-pc-windows-msvc.zip"
    url = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/{asset}"
    zip_path = download(url, DOWNLOADS / asset, UV_SHA256)
    print(f"installing uv {UV_VERSION} (Windows)")
    BIN.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(BIN)
    for exe in BIN.glob("*.exe"):
        exe.chmod(0o755)
    if not uv_exe.is_file():
        fail(f"uv.exe not found after extracting {zip_path.name}")


def ensure_python(wine: str) -> None:
    uv_exe = str(BIN / "uv.exe")
    check = subprocess.run(
        [wine, uv_exe, "python", "find", PYTHON_VERSION],
        env=wine_env(),
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        print(f"Python {PYTHON_VERSION} (Windows) installed: {check.stdout.strip()}")
        return
    print(f"installing Python {PYTHON_VERSION} (Windows, via uv)")
    run_wine([wine], [uv_exe, "python", "install", PYTHON_VERSION], timeout=600)


def ensure_innosetup(wine: str) -> Path:
    """Install Inno Setup in the prefix and return the path to ISCC.exe."""
    if ISCC.is_file():
        print(f"Inno Setup {INNOSETUP_VERSION} installed")
        return ISCC
    asset = f"innosetup-{INNOSETUP_VERSION}-x64.exe"
    tag = f"is-{INNOSETUP_VERSION.replace('.', '_')}"
    url = f"https://github.com/jrsoftware/issrc/releases/download/{tag}/{asset}"
    installer = download(url, DOWNLOADS / asset, INNOSETUP_SHA256)
    # /SILENT still creates hidden windows, so it needs a display (xvfb if headless)
    print(f"installing Inno Setup {INNOSETUP_VERSION}")
    run_wine(
        display_wine_cmd(wine),
        [str(installer), "/SILENT", "/ALLUSERS", "/NORESTART", f"/DIR={INNO_DIR}", f"/LOG=C:\\{INNO_LOG}"],
        check=False,
    )
    if not ISCC.is_file():
        log = PREFIX / "drive_c" / INNO_LOG
        tail = "\n".join(log.read_text(errors="replace").splitlines()[-15:]) if log.is_file() else ""
        detail = f"\ninstaller log:\n{tail}" if tail else ""
        fail(f"Inno Setup install did not produce {ISCC}{detail}")
    return ISCC


def ensure(wine: str) -> Path:
    """Idempotently create the full wine environment. Returns the path to ISCC.exe."""
    ensure_prefix(wine)
    ensure_uv()
    ensure_python(wine)
    iscc = ensure_innosetup(wine)
    print(f"wine environment ready ({WINE_ROOT.relative_to(ROOT)})")
    return iscc


def main() -> int:
    ensure(find_wine())
    return 0


if __name__ == "__main__":
    sys.exit(main())
