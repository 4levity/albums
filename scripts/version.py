"""Print or write the albums package version derived from git tags.

The setuptools-scm options below must match the ``[tool.hatch.version]``
section in pyproject.toml so that this script computes the same version as
building or installing the package.
"""

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


def main() -> int:
    """Print the version, or write it to src/albums/_version.py with ``write``."""
    version = get_albums_version()
    if len(sys.argv) > 1 and sys.argv[1] == "write":
        dump_version(".", version, "src/albums/_version.py")
        print(f"wrote src/albums/_version.py: {version}")
    else:
        print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
