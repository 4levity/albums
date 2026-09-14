"""Build the Windows installer from this repo on Linux, using wine.

Creates the wine environment if needed (scripts/wine_setup.py), then runs the
same steps as the Windows CI job: `uv sync` from uv.lock into the wine venv,
write the version, render the installer script, pyinstaller, and Inno Setup's
iscc. Writes dist/installer/albums_win_x86_64-<version>-setup.exe.

Usage: python scripts/wine_build.py
"""

import subprocess
import sys
from pathlib import Path

# allow package imports (scripts.*) when run as a plain script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import wine_common, wine_setup  # noqa: E402

# sysconfig.get_platform() of the 64-bit Windows Python; the .iss [Files]
# source path expects dist/pyinstaller/win_amd64
PLATFORM = "win_amd64"


def main() -> int:
    wine = wine_common.find_wine()
    try:
        iscc = wine_setup.ensure(wine)
        print("syncing wine venv from uv.lock")
        wine_common.run_wine([wine], [str(wine_common.BIN / "uv.exe"), "sync", "--locked"], timeout=3600)
        print("writing version")
        subprocess.run(["uv", "run", "python", "scripts/version.py", "write"], cwd=wine_common.ROOT, check=True)
        print("rendering installer script")
        subprocess.run(["uv", "run", "python", "scripts/render_iss.py"], cwd=wine_common.ROOT, check=True)
        print(f"building pyinstaller executable ({PLATFORM})")
        wine_common.run_wine(
            [wine],
            [
                str(wine_common.BIN / "uv.exe"),
                "run",
                "pyinstaller",
                "src/albums/__main__.py",
                "--onedir",
                "--name",
                "albums",
                "--noconfirm",
                "--clean",
                "--collect-data",
                "albums",
                "--workpath",
                f"build/{PLATFORM}",
                "--distpath",
                f"dist/pyinstaller/{PLATFORM}",
                "--specpath",
                f"build/{PLATFORM}/.specs",
                "--contents-directory",
                "_albums_internal",
            ],
            timeout=3600,
        )
        print("compiling installer with Inno Setup")
        wine_common.run_wine([wine], [str(iscc), r"build\albums.iss"], timeout=1800)
        exes = sorted((wine_common.ROOT / "dist" / "installer").glob("*.exe"))
        if not exes:
            wine_common.fail("no installer found in dist/installer")
        for exe in exes:
            print(f"installer: {exe} ({exe.stat().st_size / 1024 / 1024:.1f} MiB)")
    finally:
        wine_common.kill_wineserver()
    return 0


if __name__ == "__main__":
    sys.exit(main())
