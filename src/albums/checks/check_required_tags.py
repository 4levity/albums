from ..library.metadata import album_is_basic_taggable
from ..types import Album
from .base_check import Check, CheckResult, ProblemCategory


# deprecated, replace with checks for individual important tags
class CheckRequiredTags(Check):
    name = "required_tags"
    default_config = {"enabled": True, "tags": ["artist", "title"]}

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None  # this check only makes sense for files with common tags

        required_tags = self.check_config.get("tags", CheckRequiredTags.default_config["tags"])
        if not isinstance(required_tags, list):
            raise ValueError("required_tags.tag configuration must be a list of tags")

        missing_required_tags: dict[str, int] = {}
        for track in sorted(album.tracks, key=lambda track: track.filename):
            for tag in required_tags:  # pyright: ignore[reportUnknownVariableType]
                if not isinstance(tag, str):
                    raise ValueError("required_tags.tag each tag must be a string")
                if tag != "" and tag not in track.tags:
                    missing_required_tags[tag] = missing_required_tags.get(tag, 0) + 1

        if len(missing_required_tags) > 0:
            return CheckResult(ProblemCategory.TAGS, f"tracks missing required tags {missing_required_tags}")
