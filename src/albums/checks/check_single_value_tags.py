from pathlib import Path
from typing import Any
import yaml

from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album
from .base_check import Fixer, ProblemCategory, Check, CheckResult
from .helpers import describe_track_number, ordered_tracks


OPTION_CONCATENATE_SLASH = ">> Concatenate into a single value with '/' between"
OPTION_CONCATENATE_DASH = ">> Concatenate into a single value with '-' between"


class CheckSingleValueTags(Check):
    name = "single_value_tags"
    default_config = {"enabled": True, "tags": ["artist", "title"]}
    # TODO: config option to provide a single way to concatenate tag values and enable automatic fix

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
            option_free_text = False
            option_automatic_index = None
            return CheckResult(
                ProblemCategory.TAGS,
                f"conflicting values for single value tags\n{yaml.dump(multiple_value_tags)}",
                Fixer(
                    lambda option: self._fix(album, option),
                    [OPTION_CONCATENATE_SLASH, OPTION_CONCATENATE_DASH],
                    option_free_text,
                    option_automatic_index,
                    (["track", "filename"], [[describe_track_number(track), track.filename] for track in ordered_tracks(album)]),
                ),
            )

    def _fix(self, album: Album, option: str) -> bool:
        if option == OPTION_CONCATENATE_DASH:
            concat = " - "
        elif option == OPTION_CONCATENATE_SLASH:
            concat = " / "
        else:
            raise ValueError(f"invalid option {option}")

        changed = False
        for track in album.tracks:
            file = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / track.filename
            new_values: list[tuple[str, str | None]] = []
            for tag_name in self.single_value_tags:
                if tag_name in track.tags and len(track.tags[tag_name]) > 1:
                    new_value = concat.join(track.tags[tag_name])
                    new_values.append((tag_name, new_value))
                    changed = True
            if new_values:
                self.ctx.console.print(f"setting {' and '.join(list(name for (name, _) in new_values))} on {track.filename}")
                set_basic_tags(file, new_values)
                changed = True

        return changed
