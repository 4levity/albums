"""Print or write the albums package version derived from git tags.

The setuptools-scm options below must match the ``[tool.hatch.version]``
section in pyproject.toml so that this script computes the same version as
building or installing the package.
"""

import re
import sys

from setuptools_scm import dump_version, get_version


def get_albums_version() -> str:
    """Return the PEP 440 version for the current git checkout."""
    return str(
        get_version(
            root=".",
            version_scheme="post-release",
            fallback_version="0.0.0",
        )
    )


def get_file_version(version: str) -> str:
    """Return a 4-part numeric file version (e.g. 1.2.3.0) for Windows file metadata."""
    core = re.split(r"\.post|\.dev|\+", version, maxsplit=1)[0]
    parts = core.split(".") + ["0"] * 4
    return ".".join(parts[:4])


def main() -> int:
    """Print the version, the 4-part file version with ``fileversion``, or write
    the version to src/albums/_version.py with ``write``."""
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    version = get_albums_version()
    if command == "write":
        dump_version(".", version, "src/albums/_version.py")
        print(f"wrote src/albums/_version.py: {version}")
    elif command == "fileversion":
        print(get_file_version(version))
    else:
        print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
