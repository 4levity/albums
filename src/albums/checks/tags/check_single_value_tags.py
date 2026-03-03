from collections import OrderedDict
from typing import Any, Sequence

import yaml
from rich.markup import escape

from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import BASIC_TAGS, BasicTag
from ...types import Album, CheckResult, Fixer
from ..base_check import Check
from ..helpers import describe_track_number, ordered_tracks

OPTION_CONCATENATE_WITH = ">> Concatenate unique values into one with "
OPTION_REMOVE_DUPLICATES_ONLY = ">> Remove duplicate values (preserve unique multiple values)"


class CheckSingleValueTags(Check):
    name = "single-value-tags"
    default_config = {"enabled": True, "tags": ["artist", "title"], "concatenators": [" / ", "/", " - "], "automatic_concatenate": True}

    def init(self, check_config: dict[str, Any]):
        tags: list[str] = check_config.get("tags", CheckSingleValueTags.default_config["tags"])
        if not isinstance(tags, list) or any(not isinstance(tag, str) or tag not in BASIC_TAGS for tag in tags):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError(f"single-value-tags.tags configuration must be a list of supported tags: {', '.join(BASIC_TAGS)}")
        self.single_value_tags = list(BasicTag(tag) for tag in tags)

        concatenators: list[str] = check_config.get("concatenators", CheckSingleValueTags.default_config["concatenators"])
        if not isinstance(concatenators, list) or any(not isinstance(concatenator, str) for concatenator in concatenators):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError("single-value-tags.concatenators configuration must be a list of strings")
        self.concatenators = concatenators
        self.automatic_concatenate = bool(check_config.get("automatic_concatenate", CheckSingleValueTags.default_config["automatic_concatenate"]))

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_TAGS) for track in album.tracks):
            return None  # this check only makes sense for files with common tags

        multiple_value_tags: list[dict[str, dict[str, Sequence[str]]]] = []
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
            for concatenator in self.concatenators:
                options.append(f'{OPTION_CONCATENATE_WITH}"{concatenator}"')
            option_automatic_index = 0 if duplicates or self.automatic_concatenate else None
            return CheckResult(
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
        if option.startswith(OPTION_CONCATENATE_WITH):
            concat = option[len(OPTION_CONCATENATE_WITH) + 1 : -1]
        elif option == OPTION_REMOVE_DUPLICATES_ONLY:
            concat = None
        else:
            raise ValueError(f"invalid option {option}")

        changed = False
        for track in album.tracks:
            file = self.ctx.config.library / album.path / track.filename
            new_values: list[tuple[BasicTag, str | list[str] | None]] = []
            for tag in self.single_value_tags:
                if tag in track.tags and len(track.tags[tag]) > 1:
                    unique_values = list(OrderedDict.fromkeys(track.tags[tag]))
                    if concat:
                        unique_values = [concat.join(unique_values)]
                    new_values.append((tag, unique_values))
                    changed = True
            if new_values:
                self.ctx.console.print(f"setting {' and '.join(list(name for (name, _) in new_values))} on {track.filename}")
                self.tagger.get(album.path).set_basic_tags(file, new_values)
                changed = True

        return changed
