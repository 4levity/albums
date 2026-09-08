try:
    from albums._version import __version__  # pyright: ignore[reportMissingImports]
except ImportError:
    # _version.py is generated from git tags at install/build time
    # (see [tool.hatch.version] in pyproject.toml and scripts/version.py)
    __version__ = "0.0.0"

__version__: str
