"""Build the Windows installer from this repo on Linux, using wine.

Creates the wine environment if needed (scripts/wine_setup.py), then runs the
same steps as the Windows CI job: `uv sync` from uv.lock into the wine venv,
write the version, render the installer script and project icon, pyinstaller,
and Inno Setup's iscc. Writes dist/installer/albums_win_x86_64-<version>-setup.exe.

Usage: python scripts/wine_build.py
"""

import os
import sys
from pathlib import Path

# allow package imports (scripts.*) when run as a plain script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import wine_common, wine_setup  # noqa: E402

# sysconfig.get_platform() of the 64-bit Windows Python; the .iss [Files]
# source path expects dist/pyinstaller/win_amd64
PLATFORM = "win_amd64"


def build_setup(wine: str) -> None:
    """Build the installer in dist/installer/ (the steps in the module docstring).

    Needs the wine environment from wine_setup.ensure, and leaves the build
    prefix's wineserver running for the caller to kill.
    """
    print("syncing wine venv from uv.lock")
    # only the groups this build needs (not the defaults): the installer build
    # runs pyinstaller under wine, the host venv does the version.py steps
    group_args = os.environ.get("UV_GROUP_ARGS", "").split()
    wine_common.run_wine(
        [wine],
        [str(wine_common.BIN / "uv.exe"), "sync", "--locked", *group_args],
        prefix=wine_common.BUILD_PREFIX,
        timeout=3600,
    )
    print("writing version")
    wine_common.uv_run(["python", "scripts/version.py", "write"], check=True)
    print("rendering installer script")
    wine_common.uv_run(["python", "scripts/render_iss.py"], check=True)
    print("rendering project icon")
    wine_common.uv_run(["python", "scripts/render_icon.py"], check=True)
    print(f"building pyinstaller executable ({PLATFORM})")
    wine_common.run_wine(
        [wine],
        [
            str(wine_common.BIN / "uv.exe"),
            "run",
            *group_args,
            "pyinstaller",
            "src/albums/__main__.py",
            "--onedir",
            "--name",
            "albums",
            "--noconfirm",
            "--clean",
            "--collect-data",
            "albums",
            # absolute path: PyInstaller resolves relative --icon paths against
            # the spec file's directory, and the wine process sees the POSIX
            # root as the Z: drive
            "--icon",
            "Z:/" + Path("build/icon.ico").resolve().as_posix().lstrip("/"),
            "--workpath",
            f"build/{PLATFORM}",
            "--distpath",
            f"dist/pyinstaller/{PLATFORM}",
            "--specpath",
            f"build/{PLATFORM}/.specs",
            "--contents-directory",
            "_albums_internal",
        ],
        prefix=wine_common.BUILD_PREFIX,
        timeout=3600,
    )
    print("compiling installer with Inno Setup")
    wine_common.run_wine([wine], [str(wine_common.ISCC), r"build\albums.iss"], prefix=wine_common.BUILD_PREFIX, timeout=1800)
    exes = sorted((wine_common.ROOT / "dist" / "installer").glob("*.exe"))
    if not exes:
        wine_common.fail("no installer found in dist/installer")
    for exe in exes:
        print(f"installer: {exe} ({exe.stat().st_size / 1024 / 1024:.1f} MiB)")


def main() -> int:
    wine = wine_common.find_wine()
    try:
        wine_setup.ensure(wine)
        build_setup(wine)
    finally:
        wine_common.kill_wineserver(wine_common.BUILD_PREFIX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
