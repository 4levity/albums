"""Print or write the albums package version derived from git tags.

The setuptools-scm options below must match the ``[tool.hatch.version]``
section in pyproject.toml so that this script computes the same version as
building or installing the package.
"""

import sys
from pathlib import Path

from setuptools_scm import dump_version, get_version

# allow package imports (scripts.fileversion) when run as a plain script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import fileversion  # noqa: E402 (import not at top of file, see above)


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
    """Print the version, the 4-part file version (the Windows installer
    filename part, scripts/fileversion.py) with ``fileversion``, or write the
    version to src/albums/_version.py with ``write``."""
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    version = get_albums_version()
    if command == "write":
        # scm_version=None: we only dump the computed string, not ScmVersion data
        dump_version(".", version, "src/albums/_version.py", scm_version=None)
        print(f"wrote src/albums/_version.py: {version}")
    elif command == "fileversion":
        print(fileversion.file_version(version))
    else:
        print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
