"""Render derived images from the project icon (docs/art/icon.png).

docs/images/favicon.png and docs/images/logo.png go into the zensical docs
site (browser tab and header logo), and build/icon.ico goes into the Windows
builds: PyInstaller uses it for the albums.exe icon and Inno Setup's
SetupIconFile for the setup.exe and wizard icons.
"""

import sys
from pathlib import Path

from PIL import Image

SOURCE = "docs/art/icon.png"
FAVICON = "docs/images/favicon.png"
LOGO = "docs/images/logo.png"
ICO = "build/icon.ico"
FAVICON_SIZE = 48
LOGO_SIZE = 128
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def render_png(source: Path, destination: Path, size: int) -> None:
    """Resize the master icon to size x size and write it as a PNG."""
    with Image.open(source) as img:
        resized = img.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    resized.save(destination)


def render_ico(source: Path, destination: Path, sizes: list[int]) -> None:
    """Resize the master icon to each square size and write a multi-size ICO."""
    with Image.open(source) as img:
        ico = img.convert("RGBA")
    destination.parent.mkdir(parents=True, exist_ok=True)
    ico.save(destination, sizes=[(size, size) for size in sizes])


def main() -> int:
    """Write the derived icon images from the master icon."""
    source = Path(SOURCE)
    if not source.exists():
        print(f"error: master icon {SOURCE} not found", file=sys.stderr)
        return 1
    render_png(source, Path(FAVICON), FAVICON_SIZE)
    render_png(source, Path(LOGO), LOGO_SIZE)
    render_ico(source, Path(ICO), ICO_SIZES)
    print(f"rendered {FAVICON}, {LOGO} and {ICO} from {SOURCE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
