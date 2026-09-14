"""Run the test suite in the wine venv (make wine-pytest).

Usage: python scripts/wine_pytest.py
"""

import sys
from pathlib import Path

# allow package imports (scripts.*) when run as a plain script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import wine_common, wine_setup


def main() -> int:
    wine = wine_common.find_wine()
    try:
        wine_setup.ensure(wine)
        print("running test suite under wine")
        wine_common.run_wine(
            [wine], [str(wine_common.BIN / "uv.exe"), "run", "pytest", "-o", "console_output_style=none", "--max-warnings=0"], timeout=3600
        )
    finally:
        wine_common.kill_wineserver()
    return 0


if __name__ == "__main__":
    sys.exit(main())
