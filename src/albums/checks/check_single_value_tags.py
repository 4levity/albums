from ..types import Album
from .base_check import Check, CheckResult


class CheckSingleValueTags(Check):
    name = "single_value_tags"
    default_config = {"enabled": True, "tags": ["title", "tracknumber", "tracktotal"]}

    def check(self, album: Album):
        single_value_tags = self.config.get("tags", CheckSingleValueTags.default_config["tags"])
        multiple_values = {}
        for track in sorted(album.tracks, key=lambda track: track.filename):
            for tag in single_value_tags:
                if tag in track.tags and len(track.tags[tag]) > 1:
                    multiple_values[tag] = multiple_values.get(tag, 0) + 1

        if len(multiple_values) > 0:
            return CheckResult(self.name, f"conflicting values for single value tags {multiple_values}")
