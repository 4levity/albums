"""Install, run and uninstall the Inno Setup installer in a temporary wine
prefix (make wine-e2e).

By default the installer is not rebuilt: it must already exist in
dist/installer/ with a name matching the current version (make wine-build
builds it), and a warning that it may be stale is printed. With --build a
fresh installer is built first (like make wine-build, creating the wine
environment if needed) and the warning is skipped. The warning is also
suppressed in CI (GITHUB_ACTIONS set), where the workflow builds the
installer in the same run.

Usage: python scripts/wine_e2e.py [--build]
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# allow package imports (scripts.*) when run as a plain script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import wine_build, wine_common, wine_setup

# temporary prefix the installer is tested in, recreated on every run
E2E_PREFIX = wine_common.ROOT / "build" / "wine-e2e"

INSTALLER_SWITCHES = ["/VERYSILENT", "/SUPPRESSMSGBOXES"]
# Inno Setup logs, written inside the prefix (on the host under
# <prefix>/drive_c/) for troubleshooting
INSTALL_LOG = "C:\\albums-install.log"
UNINSTALL_LOG = "C:\\albums-uninstall.log"
# registry key the installer code in scripts/albums.iss creates
INSTALLER_REG_KEY = r"HKCU\Software\4levity\albums"
# uninstall entry for the AppId in scripts/albums.iss
UNINSTALL_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{d03e11ba-65f7-48f2-a94f-4fabbd041213}_is1"


def current_version() -> str:
    return wine_common.uv_run(
        ["python", "scripts/version.py"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def find_installer(just_built: bool) -> Path:
    """Return the installer in dist/installer/ matching the current version.

    The name pattern is a contract with scripts/albums.iss (OutputBaseFilename)
    and .github/workflows/release.yml (which downloads the artifact by this
    name); only the file version (scripts/fileversion.py) in it may vary.
    """
    file_version = wine_common.uv_run(
        ["python", "scripts/version.py", "fileversion"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    installer = wine_common.ROOT / "dist" / "installer" / f"albums_win_x86_64-{file_version}-setup.exe"
    if not installer.is_file():
        wine_common.fail(f"no installer for version {file_version} in dist/installer; run `make wine-build` first")
    if not just_built and not os.environ.get("GITHUB_ACTIONS"):
        print("WARNING: using an existing installer build from dist/installer, not one built by this run:")
        print(f"WARNING:   {installer.relative_to(wine_common.ROOT)}")
        print("WARNING: if the source changed since it was built, rebuild it with `make wine-build` or rerun this script with --build")
    return installer


def clean_path_entry(entry: str) -> str:
    """Normalize a PATH entry for comparison (mirrors CleanPathEntry in scripts/albums.iss)."""
    entry = entry.strip()
    if len(entry) >= 2 and entry.startswith('"') and entry.endswith('"'):
        entry = entry[1:-1]
    return entry.rstrip("\\").lower()


def to_host(prefix: Path, win_path: str) -> Path:
    """Convert a drive-qualified Windows path to its host path under the wine prefix."""
    drive, sep, rest = win_path.partition(":")
    if len(drive) != 1 or not drive.isalpha() or not sep:
        wine_common.fail(f"unexpected Windows path: {win_path!r}")
    return prefix / f"drive_{drive.lower()}" / rest.replace("\\", "/").lstrip("/")


def print_failure_logs(prefix: Path) -> None:
    """Print the Inno log tails; the prefix stays under build/ for inspection."""
    for win_log in (INSTALL_LOG, UNINSTALL_LOG):
        log = to_host(prefix, win_log)
        if log.is_file():
            print(f"--- {log.name} (last 40 lines) ---")
            print("\n".join(log.read_text(errors="replace").splitlines()[-40:]))
    print(f"failed wine prefix kept for inspection: {prefix}")


def test_installer(wine: str, installer: Path) -> None:
    print("testing installer in a temporary wine prefix")
    # a wineserver left by a killed run would be reused by the first wine
    # command with stale state, so kill it before removing the old prefix
    wine_common.kill_wineserver(E2E_PREFIX)
    shutil.rmtree(E2E_PREFIX, ignore_errors=True)
    E2E_PREFIX.mkdir(parents=True)
    try:
        _test_installer_steps(wine, installer, E2E_PREFIX)
    except BaseException:
        try:
            print_failure_logs(E2E_PREFIX)
        except BaseException:
            print("could not print failure logs", file=sys.stderr)
        raise
    finally:
        wine_common.kill_wineserver(E2E_PREFIX)
    print("installer test passed")


def _test_installer_steps(wine: str, installer: Path, prefix: Path) -> None:
    def wine_cmd(args: list[str], timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
        return wine_common.wine_capture([wine], args, timeout=timeout, check=check, prefix=prefix)

    def reg_value(key: str, name: str) -> str | None:
        proc = wine_cmd(["reg", "query", key, "/v", name], timeout=120, check=False)
        if proc.returncode != 0:
            return None
        pattern = re.compile(rf"^\s+{re.escape(name)}\s+REG_\w+\s*(.*)$")
        for line in proc.stdout.splitlines():
            if (match := pattern.match(line)) is not None:
                return match.group(1).strip()
        wine_common.fail(f"could not parse value {name!r} of {key} from: {proc.stdout!r}")

    def reg_key_exists(key: str) -> bool:
        return wine_cmd(["reg", "query", key], timeout=120, check=False).returncode == 0

    def path_entries() -> list[str]:
        path = reg_value(r"HKCU\Environment", "Path")
        if path is None:
            return []
        return [clean_path_entry(entry) for entry in path.split(";")]

    # the installer is a GUI app, so it needs a display (xvfb when headless)
    print("--- install ---")
    wine_common.run_wine(wine_common.display_wine_cmd(wine), [str(installer), *INSTALLER_SWITCHES, f"/LOG={INSTALL_LOG}"], timeout=900, prefix=prefix)

    print("--- verify install ---")
    local_appdata = wine_cmd(["cmd", "/c", "echo %LOCALAPPDATA%"]).stdout.strip()
    appdir_win = f"{local_appdata}\\Programs\\albums"
    appdir = to_host(prefix, appdir_win)
    if not (appdir / "albums.exe").is_file():
        wine_common.fail(f"albums.exe not installed in {appdir} after install")
    print(f"installed: {appdir_win}")
    if reg_value(INSTALLER_REG_KEY, "AddedToUserPath") != "yes":
        wine_common.fail(f"{INSTALLER_REG_KEY} AddedToUserPath is not 'yes' after install")
    print("registry: AddedToUserPath=yes")
    if clean_path_entry(appdir_win) not in path_entries():
        wine_common.fail(f"app directory not added to the user PATH after install: {appdir_win}")
    print("added to user PATH")

    print("--- run albums --version ---")
    # the dirty-tree date suffix (.dYYYYMMDD) varies with local edits, so compare without it
    expected = re.sub(r"\.d\d+$", "", current_version())
    output = wine_cmd(["cmd", "/c", "albums", "--version"]).stdout
    if expected not in output:
        wine_common.fail(f"albums --version does not report {expected}: {output.strip()!r}")
    print(f"runs: albums --version -> {expected}")

    print("--- uninstall ---")
    uninstallers = sorted(appdir.glob("unins*.exe"))
    if len(uninstallers) != 1:
        wine_common.fail(f"expected one uninstaller in {appdir}, found {len(uninstallers)}")
    # the uninstaller defers removing its own directory until it exits, so run
    # it from a batch file that sleeps 5s afterwards: the display (xvfb when
    # headless) then stays alive until the batch exits, not when wine exits
    uninstaller_win = f"{appdir_win}\\{uninstallers[0].name}"
    uninstall_bat = r"C:\albums-uninstall.bat"
    uninstall_bat_text = (
        "@echo off\r\n"
        f'"{uninstaller_win}" {" ".join(INSTALLER_SWITCHES)} /LOG={UNINSTALL_LOG}\r\n'
        "set code=%errorlevel%\r\n"
        "ping -n 6 127.0.0.1 >nul\r\n"
        "exit /b %code%\r\n"
    )
    to_host(prefix, uninstall_bat).write_text(uninstall_bat_text)
    wine_common.run_wine(wine_common.display_wine_cmd(wine), ["cmd", "/c", uninstall_bat], timeout=900, prefix=prefix)

    print("--- verify uninstall ---")
    if appdir.is_dir():
        wine_common.fail(f"app directory still exists after uninstall: {appdir}")
    if clean_path_entry(appdir_win) in path_entries():
        wine_common.fail("app directory still on the user PATH after uninstall")
    if reg_key_exists(INSTALLER_REG_KEY):
        wine_common.fail(f"{INSTALLER_REG_KEY} still exists after uninstall")
    if reg_key_exists(UNINSTALL_KEY):
        wine_common.fail(f"{UNINSTALL_KEY} still exists after uninstall")
    print("uninstalled")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install, run and uninstall the Inno Setup installer in a temporary wine prefix")
    parser.add_argument(
        "--build", action="store_true", help="build a fresh installer first (like make wine-build, creating the wine environment if needed)"
    )
    args = parser.parse_args()
    wine = wine_common.find_wine()
    if args.build:
        try:
            wine_setup.ensure(wine)
            print("building installer")
            wine_build.build_setup(wine)
        finally:
            # the build ran in the build prefix; flush its server
            wine_common.kill_wineserver(wine_common.BUILD_PREFIX)
    installer = find_installer(just_built=args.build)
    test_installer(wine, installer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
