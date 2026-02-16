from typing import Any

from ..library.metadata import album_is_basic_taggable
from ..types import Album, CheckResult, ProblemCategory
from .base_check import Check


# deprecated, replace with checks for individual important tags
class CheckRequiredTags(Check):
    name = "required_tags"
    default_config = {"enabled": False, "tags": ["artist", "title"]}

    def init(self, check_config: dict[str, Any]):
        required_tags: list[Any] = check_config.get("tags", CheckRequiredTags.default_config["tags"])
        if not isinstance(required_tags, list) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(tag, str) or tag == "" for tag in required_tags
        ):
            raise ValueError("required_tags.tags configuration must be a list of tags")
        self.required_tags = list(str(tag) for tag in required_tags)

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None  # this check only makes sense for files with common tags

        missing_required_tags: dict[str, int] = {}
        for track in sorted(album.tracks, key=lambda track: track.filename):
            for tag in filter(lambda tag: tag not in track.tags, self.required_tags):
                missing_required_tags[tag] = missing_required_tags.get(tag, 0) + 1

        if len(missing_required_tags) > 0:
            return CheckResult(ProblemCategory.TAGS, f"tracks missing required tags {missing_required_tags}")
