"""Print the 4-part Windows file version for a PEP 440 albums version.

The file version is embedded in the Windows installer filename, which CI
downloads by name, so the conversion lives in one dependency-free script
that runs on any Python 3 (e.g. a CI runner without the project
installed).

Usage: python scripts/fileversion.py VERSION
"""

import re
import sys


def file_version(version: str) -> str:
    """Return a 4-part numeric file version (e.g. 1.2.3.0) for Windows file metadata.

    The fourth part is the post/dev release number (at least 1) if present,
    else 0, so file versions sort with the releases they came from.
    """
    match = re.search(r"\.(post|dev)(\d+)", version)
    core = version[: match.start()] if match else version
    fourth = max(int(match.group(2)), 1) if match else 0
    parts = core.split(".") + [str(fourth)] * 5
    return ".".join(parts[:4])


def main() -> int:
    """Print the file version of the VERSION command line argument."""
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} VERSION", file=sys.stderr)
        return 1
    print(file_version(sys.argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
