"""Render build/albums.iss from the scripts/albums.iss template.

The template holds 0.0.0 placeholder versions so it is a directly
compilable Inno Setup script; this replaces them with the current
versions (post/dev versions are truncated before their + local part).
The output is one directory under the repo root, the same depth as the
template, so the template's relative paths keep working.

Usage: python scripts/render_iss.py
"""

import re
import sys
from pathlib import Path

# allow package imports (scripts.version) when run as a plain script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import version  # noqa: E402

TEMPLATE = "scripts/albums.iss"
OUTPUT = "build/albums.iss"


def render_installer_script(template: str, app_version: str, file_version: str) -> str:
    """Replace the 0.0.0 placeholder versions in the installer script template.

    The lookarounds match standalone placeholders only, and 0.0.0.0 goes
    first so 0.0.0 does not match inside it. Comment lines are skipped so
    the placeholder documentation survives rendering.
    """
    lines: list[str] = []
    for line in template.split("\n"):
        if not line.lstrip().startswith(";"):
            line = re.sub(r"(?<![\d.])0\.0\.0\.0(?![\d.])", file_version, line)
            line = re.sub(r"(?<![\d.])0\.0\.0(?![\d.])", app_version, line)
        lines.append(line)
    return "\n".join(lines)


def display_version(version: str) -> str:
    """Return the version for installer display, dropping the + local part of
    post/dev versions (e.g. 0.9.31.post9+g1234abcd.d20260911 -> 0.9.31.post9)."""
    if re.search(r"\.(post|dev)\d+", version):
        return version.split("+", 1)[0]
    return version


def main() -> int:
    """Write the installer script rendered with the current version."""
    template_text = Path(TEMPLATE).read_text()
    if "0.0.0" not in template_text:
        print(f"error: {TEMPLATE} has no 0.0.0 placeholder versions", file=sys.stderr)
        return 1
    full_version = version.get_albums_version()
    app_version = display_version(full_version)
    output = Path(OUTPUT)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_installer_script(template_text, app_version, version.get_file_version(full_version)))
    print(f"wrote {output}: {app_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
