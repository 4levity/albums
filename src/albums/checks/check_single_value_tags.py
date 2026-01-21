from albums.library.metadata import album_is_basic_taggable
from ..types import Album
from .base_check import Check, CheckResult


class CheckSingleValueTags(Check):
    name = "single_value_tags"
    default_config = {"enabled": True, "tags": ["title", "tracknumber", "tracktotal"]}

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None  # this check only makes sense for files with common tags

        single_value_tags = self.config.get("tags", CheckSingleValueTags.default_config["tags"])
        multiple_value_tags: list[dict] = []
        for track in sorted(album.tracks, key=lambda track: track.filename):
            for tag_name in single_value_tags:
                # check for multiple values for tag_name
                if tag_name in track.tags and len(track.tags[tag_name]) > 1:
                    multiple_value_tags.append({track.filename: {tag_name: track.tags[tag_name]}})

        if len(multiple_value_tags) > 0:
            return CheckResult(self.name, f"conflicting values for single value tags {multiple_value_tags}")
