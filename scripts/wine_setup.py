"""Create the wine environment for building the Windows installer on Linux.

Idempotent. Creates a wine prefix in the gitignored `.cache/wine/` folder and
installs into it: uv (which downloads the Windows Python the build uses) and
Inno Setup. Requires wine 11.0 or newer; on headless systems the Inno Setup
installer runs under xvfb-run, which needs the xvfb package.

Usage: python scripts/wine_setup.py
"""

import shutil
import sys
import zipfile
from pathlib import Path

# allow package imports (scripts.wine_common) when run as a plain script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import wine_common  # noqa: E402

DOWNLOADS = wine_common.WINE_ROOT / "downloads"

# Pinned releases and the sha256 of their release assets. Python is not
# pinned: uv picks the latest 3.14.x, as the Windows CI job does.
UV_VERSION = "0.12.16"
UV_SHA256 = "f730454bf09019754e5e5abd71a8aa18683cb739cba0d9c720bac2e7c901160f"  # uv-x86_64-pc-windows-msvc.zip
INNOSETUP_VERSION = "7.1.0"
INNOSETUP_SHA256 = "0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f"  # innosetup-7.1.0-x64.exe
PYTHON_VERSION = "3.14"
# deterministic Inno Setup install location, passed to its own installer via /DIR
INNO_DIR = r"C:\InnoSetup7"
INNO_LOG = "inno-setup-install.log"


def ensure_prefix(wine: str) -> None:
    if (wine_common.BUILD_PREFIX / "drive_c").is_dir():
        print("wine prefix exists")
        return
    print(f"creating wine prefix in {wine_common.BUILD_PREFIX.relative_to(wine_common.ROOT)}")
    wine_common.WINE_ROOT.mkdir(parents=True, exist_ok=True)
    # a fresh prefix's X support only initializes when wineboot runs on a display
    wine_common.run_wine(wine_common.display_wine_cmd(wine), ["wineboot", "--init"], prefix=wine_common.BUILD_PREFIX, timeout=300)
    if not (wine_common.BUILD_PREFIX / "drive_c").is_dir():
        wine_common.fail(f"wineboot did not create {wine_common.BUILD_PREFIX.relative_to(wine_common.ROOT)}/drive_c")


def ensure_uv() -> None:
    uv_exe = wine_common.BIN / "uv.exe"
    if uv_exe.is_file():
        print(f"uv {UV_VERSION} (Windows) installed")
        return
    asset = "uv-x86_64-pc-windows-msvc.zip"
    url = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/{asset}"
    zip_path = wine_common.download(url, DOWNLOADS / asset, UV_SHA256)
    print(f"installing uv {UV_VERSION} (Windows)")
    wine_common.BIN.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(wine_common.BIN)
    for exe in wine_common.BIN.glob("*.exe"):
        exe.chmod(0o755)
    if not uv_exe.is_file():
        wine_common.fail(f"uv.exe not found after extracting {zip_path.name}")


def ensure_python(wine: str) -> None:
    uv_exe = str(wine_common.BIN / "uv.exe")
    check = wine_common.run(
        [wine, uv_exe, "python", "find", PYTHON_VERSION],
        env=wine_common.wine_env(wine_common.BUILD_PREFIX),
        cwd=wine_common.ROOT,
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        print(f"Python {PYTHON_VERSION} (Windows) installed: {check.stdout.strip()}")
        return
    print(f"installing Python {PYTHON_VERSION} (Windows, via uv)")
    wine_common.run_wine(
        [wine],
        [uv_exe, "python", "install", PYTHON_VERSION],
        prefix=wine_common.BUILD_PREFIX,
        timeout=600,
    )


def ensure_venv() -> None:
    """Remove the wine venv if its Python no longer matches PYTHON_VERSION.

    uv reuses an existing venv even when a newer Python is installed, so a
    PYTHON_VERSION bump would otherwise silently keep the old interpreter in
    the built installer. The next `uv sync` recreates the venv with the new
    Python.
    """
    cfg = wine_common.VENV / "Scripts" / "pyvenv.cfg"
    if not cfg.is_file():
        return
    for line in cfg.read_text().splitlines():
        if line.startswith("version = "):
            venv_python = line.partition("=")[2].strip()
            if not venv_python.startswith(PYTHON_VERSION):
                print(f"removing wine venv built for Python {venv_python}; will rebuild for {PYTHON_VERSION}")
                shutil.rmtree(wine_common.VENV)
            return


def ensure_innosetup(wine: str) -> Path:
    """Install Inno Setup in the prefix and return the path to ISCC.exe."""
    if wine_common.ISCC.is_file():
        print(f"Inno Setup {INNOSETUP_VERSION} installed")
        return wine_common.ISCC
    asset = f"innosetup-{INNOSETUP_VERSION}-x64.exe"
    tag = f"is-{INNOSETUP_VERSION.replace('.', '_')}"
    url = f"https://github.com/jrsoftware/issrc/releases/download/{tag}/{asset}"
    installer = wine_common.download(url, DOWNLOADS / asset, INNOSETUP_SHA256)
    # /SILENT still creates hidden windows, so it needs a display (xvfb if headless)
    print(f"installing Inno Setup {INNOSETUP_VERSION}")
    wine_common.run_wine(
        wine_common.display_wine_cmd(wine),
        [str(installer), "/SILENT", "/ALLUSERS", "/NORESTART", f"/DIR={INNO_DIR}", f"/LOG=C:\\{INNO_LOG}"],
        prefix=wine_common.BUILD_PREFIX,
        check=False,
    )
    if not wine_common.ISCC.is_file():
        log = wine_common.BUILD_PREFIX / "drive_c" / INNO_LOG
        tail = "\n".join(log.read_text(errors="replace").splitlines()[-15:]) if log.is_file() else ""
        detail = f"\ninstaller log:\n{tail}" if tail else ""
        wine_common.fail(f"Inno Setup install did not produce {wine_common.ISCC}{detail}")
    return wine_common.ISCC


def ensure(wine: str) -> Path:
    """Idempotently create the full wine environment. Returns the path to ISCC.exe."""
    ensure_prefix(wine)
    ensure_uv()
    ensure_python(wine)
    ensure_venv()
    iscc = ensure_innosetup(wine)
    print(f"wine environment ready ({wine_common.WINE_ROOT.relative_to(wine_common.ROOT)})")
    return iscc


def main() -> int:
    try:
        ensure(wine_common.find_wine())
    finally:
        wine_common.kill_wineserver(wine_common.BUILD_PREFIX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
