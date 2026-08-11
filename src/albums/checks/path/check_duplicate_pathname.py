import logging
from collections import defaultdict

from ...entities import Album
from ..base_check import Check
from ..check_types import CheckResult

logger = logging.getLogger(__name__)


class CheckDuplicatePathname(Check):
    name = "duplicate-pathname"
    default_config = {"enabled": True}

    def check(self, album: Album):
        issues: set[str] = set()
        filenames: defaultdict[str, int] = defaultdict(int)
        for track in sorted(album.tracks):
            filenames[str.lower(track.filename)] += 1
        for picture_file in sorted(album.picture_files):
            filenames[str.lower(picture_file.filename)] += 1

        for duplicate_filename in (filename for (filename, count) in filenames.items() if count > 1):
            issues.add(f"non-unique filename - {filenames[duplicate_filename]} files are variations of {duplicate_filename}")

        # TODO also check album.path

        if issues:
            # TODO fix by automatically renaming affected files
            return CheckResult(f"duplicate filenames: {', '.join(list(issues))}")
