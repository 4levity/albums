from platformdirs import PlatformDirs

from .progress_bar import progress_bar
from .setup_logging import setup_logging


platform_dirs = PlatformDirs("albums", "4levity")


__all__ = ["platform_dirs", "progress_bar", "setup_logging"]
