from collections import OrderedDict
from typing import Any

import yaml
from rich.markup import escape

from ...library.metadata import album_is_basic_taggable, set_basic_tags
from ...types import Album, CheckResult, Fixer, ProblemCategory
from ..base_check import Check
from ..helpers import describe_track_number, ordered_tracks

OPTION_CONCATENATE_SLASH = ">> Concatenate unique values into one with '/' between"
OPTION_CONCATENATE_DASH = ">> Concatenate unique values into one with '-' between"
OPTION_REMOVE_DUPLICATES_ONLY = ">> Remove duplicate values (preserve unique multiple values)"


class CheckSingleValueTags(Check):
    name = "single-value-tags"
    default_config = {"enabled": True, "tags": ["artist", "title"]}
    # TODO: config option to provide a single way to concatenate tag values and enable automatic fix

    def init(self, check_config: dict[str, Any]):
        tags: list[Any] = check_config.get("tags", CheckSingleValueTags.default_config["tags"])
        if not isinstance(tags, list) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(tag, str) or tag == "" for tag in tags
        ):
            raise ValueError("single-value-tags.tags configuration must be a list of tags")
        self.single_value_tags = list(str(tag) for tag in tags)

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None  # this check only makes sense for files with common tags

        multiple_value_tags: list[dict[str, dict[str, list[str]]]] = []
        duplicates = False
        for track in sorted(album.tracks, key=lambda track: track.filename):
            for tag_name in self.single_value_tags:
                # check for multiple values for tag_name
                if tag_name in track.tags and len(track.tags[tag_name]) > 1:
                    multiple_value_tags.append({track.filename: {tag_name: track.tags[tag_name]}})
                    if len(set(track.tags[tag_name])) < len(track.tags[tag_name]):
                        duplicates = True

        if len(multiple_value_tags) > 0:
            option_free_text = False
            options = [OPTION_REMOVE_DUPLICATES_ONLY] if duplicates else []
            options.extend([OPTION_CONCATENATE_SLASH, OPTION_CONCATENATE_DASH])
            option_automatic_index = 0 if duplicates else None
            return CheckResult(
                ProblemCategory.TAGS,
                f"multiple values for single value tags\n{yaml.dump(multiple_value_tags)}",
                Fixer(
                    lambda option: self._fix(album, option),
                    options,
                    option_free_text,
                    option_automatic_index,
                    (["track", "filename"], [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)]),
                ),
            )

    def _fix(self, album: Album, option: str) -> bool:
        if option == OPTION_CONCATENATE_DASH:
            concat = " - "
        elif option == OPTION_CONCATENATE_SLASH:
            concat = " / "
        elif option == OPTION_REMOVE_DUPLICATES_ONLY:
            concat = None
        else:
            raise ValueError(f"invalid option {option}")

        changed = False
        for track in album.tracks:
            file = self.ctx.config.library / album.path / track.filename
            new_values: list[tuple[str, str | list[str] | None]] = []
            for tag_name in self.single_value_tags:
                if tag_name in track.tags and len(track.tags[tag_name]) > 1:
                    unique_values = list(OrderedDict.fromkeys(track.tags[tag_name]))
                    if concat:
                        unique_values = [concat.join(unique_values)]
                    new_values.append((tag_name, unique_values))
                    changed = True
            if new_values:
                self.ctx.console.print(f"setting {' and '.join(list(name for (name, _) in new_values))} on {track.filename}")
                set_basic_tags(file, new_values)
                changed = True

        return changed
