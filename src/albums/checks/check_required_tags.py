from ..types import Album
from .base import Check, CheckResult


class CheckRequiredTags(Check):
    name = "required_tags"
    default_config = "artist|title"

    def check(self, album: Album):
        required_tags = self.config.split("|")
        missing_required_tags = {}
        for track in sorted(album.tracks, key=lambda track: track.filename):
            for tag in required_tags:
                if tag != "" and tag not in track.tags:
                    missing_required_tags[tag] = missing_required_tags.get(tag, 0) + 1

        if len(missing_required_tags) > 0:
            return CheckResult(self.name, f"tracks missing required tags {missing_required_tags}")
