from typing import Any
import yaml
from ..library.metadata import album_is_basic_taggable
from ..types import Album
from .base_check import ProblemCategory, Check, CheckResult


class CheckSingleValueTags(Check):
    name = "single_value_tags"
    default_config = {"enabled": True, "tags": ["discnumber", "disctotal", "title", "tracknumber", "tracktotal"]}

    def init(self, check_config: dict[str, Any]):
        tags: list[Any] = check_config.get("tags", CheckSingleValueTags.default_config["tags"])
        if not isinstance(tags, list) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(tag, str) or tag == "" for tag in tags
        ):
            raise ValueError("single_value_tags.tags configuration must be a list of tags")
        self.single_value_tags = list(str(tag) for tag in tags)

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None  # this check only makes sense for files with common tags

        multiple_value_tags: list[dict[str, dict[str, list[str]]]] = []
        for track in sorted(album.tracks, key=lambda track: track.filename):
            for tag_name in self.single_value_tags:
                # check for multiple values for tag_name
                if tag_name in track.tags and len(track.tags[tag_name]) > 1:
                    multiple_value_tags.append({track.filename: {tag_name: track.tags[tag_name]}})

        if len(multiple_value_tags) > 0:
            return CheckResult(ProblemCategory.TAGS, f"conflicting values for single value tags\n{yaml.dump(multiple_value_tags)}")

    # could have a fixer, automatic for some cases, but haven't seen this problem o often
