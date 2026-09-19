"""Run the test suite in the wine venv (make wine-pytest).

Needs the wine environment from make wine-setup (the make target depends on it).

Usage: python scripts/wine_pytest.py
"""

import sys
from pathlib import Path

# allow package imports (scripts.*) when run as a plain script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import wine_common


def main() -> int:
    wine = wine_common.find_wine()
    try:
        print("running test suite under wine")
        # only the groups this job needs (not the defaults): the wine venv is
        # just for running pytest, unlike the host venv's GROUPS (none here)
        wine_common.run_wine(
            [wine],
            [
                str(wine_common.BIN / "uv.exe"),
                "run",
                "--no-default-groups",
                "--group",
                "test",
                "pytest",
                "-o",
                "console_output_style=none",
                "--max-warnings=0",
            ],
            prefix=wine_common.BUILD_PREFIX,
            timeout=3600,
        )
    finally:
        wine_common.kill_wineserver(wine_common.BUILD_PREFIX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
