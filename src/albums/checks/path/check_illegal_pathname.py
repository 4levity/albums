import logging
from typing import Any

from pathvalidate import ValidationError, validate_filename

from ...types import Album, CheckResult, ProblemCategory
from ..base_check import Check

logger = logging.getLogger(__name__)

COMPATIBLITY_OPTIONS = {"Linux", "Windows", "macOS", "POSIX", "universal"}  # options for pathvalidate 'platform'


class CheckIllegalPathname(Check):
    name = "illegal-pathname"
    default_config = {"enabled": True, "compatibility": "universal"}

    def init(self, check_config: dict[str, Any]):
        self.compatibility = str(check_config.get("compatibility", CheckIllegalPathname.default_config["compatibility"]))
        if self.compatibility not in COMPATIBLITY_OPTIONS:
            logger.error(f"invalid configuration: checks.illegal-pathname.compatibility must be one of {', '.join(COMPATIBLITY_OPTIONS)}")

    def check(self, album: Album):
        issues: set[str] = set()
        for track in album.tracks:
            issues = issues.union(self._check(track.filename))
        for picture_file in album.picture_files:
            issues = issues.union(self._check(picture_file))

        # TODO also check album.path

        if issues:
            # TODO fix by automatically renaming affected files
            return CheckResult(ProblemCategory.FILENAMES, f"illegal filenames: {', '.join(list(issues))}")

    def _check(self, filename: str) -> set[str]:
        try:
            validate_filename(filename, platform=self.compatibility)
            return set()
        except ValidationError as ex:
            return {f"{repr(ex)}"}
