import logging
from collections import defaultdict
from typing import Any

from pathvalidate import ValidationError, validate_filename

from ..types import Album
from .base_check import Check, CheckResult, ProblemCategory

logger = logging.getLogger(__name__)

COMPATIBLITY_OPTIONS = {"Linux", "Windows", "macOS", "POSIX", "universal"}  # options for pathvalidate 'platform'


class CheckBadPathname(Check):
    name = "bad_pathname"
    default_config = {"enabled": True, "compatibility": "universal"}

    def init(self, check_config: dict[str, Any]):
        self.compatibility = str(check_config.get("compatibility", CheckBadPathname.default_config["compatibility"]))
        if self.compatibility not in COMPATIBLITY_OPTIONS:
            logger.error(f"invalid configuration: checks.bad_pathname.compatibility must be one of {', '.join(COMPATIBLITY_OPTIONS)}")

    def check(self, album: Album):
        issues: set[str] = set()
        filenames: defaultdict[str, int] = defaultdict(int)
        for track in album.tracks:
            issues = issues.union(self._check(track.filename))
            filenames[str.lower(track.filename)] += 1
        for picture_file in album.picture_files:
            filenames[str.lower(picture_file)] += 1

        for duplicate_filename in (filename for (filename, count) in filenames.items() if count > 1):
            issues.add(f"non-unique filename - {filenames[duplicate_filename]} files are variations of {duplicate_filename}")

        # TODO also check album.path

        if issues:
            # TODO fix by automatically renaming affected files
            return CheckResult(ProblemCategory.FILENAMES, f"bad filenames: {', '.join(list(issues))}")

    def _check(self, filename: str) -> set[str]:
        try:
            validate_filename(filename, platform=self.compatibility)
            return set()
        except ValidationError as ex:
            return {f"{repr(ex)}"}
