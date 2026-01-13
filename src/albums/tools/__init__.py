from platformdirs import PlatformDirs

from .progress_bar import progress_bar
from .setup_logging import setup_logging
from .tag_reader import get_metadata


platform_dirs = PlatformDirs("albums", "4levity")
__all__ = ["platform_dirs", "progress_bar", "setup_logging", "get_metadata"]
