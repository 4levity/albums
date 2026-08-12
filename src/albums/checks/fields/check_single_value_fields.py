from collections import OrderedDict
from typing import Any, Final, Sequence

import yaml
from rich.markup import escape

from ...entities import Album
from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import BASIC_FIELDS, BasicField
from ..base_check import Check
from ..check_types import CheckResult, Fixer, FixResult
from ..helpers import describe_track_number, ordered_tracks

OPTION_CONCATENATE_WITH: Final = ">> Concatenate unique values into one with "
OPTION_REMOVE_DUPLICATES_ONLY: Final = ">> Remove duplicate values (preserve unique multiple values)"


class CheckSingleValueFields(Check):
    name = "single-value-fields"
    default_config = {"enabled": True, "fields": ["artist", "title"], "concatenators": [" / ", "/", " - "], "automatic_concatenate": True}

    def init(self, check_config: dict[str, Any]):
        fields: list[str] = check_config.get("fields", CheckSingleValueFields.default_config["fields"])
        if not isinstance(fields, list) or any(not isinstance(field_name, str) or field_name not in BASIC_FIELDS for field_name in fields):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError(f"single-value-fields.fields configuration must be a list of supported fields: {', '.join(BASIC_FIELDS)}")
        self.single_value_fields = list(BasicField(field) for field in fields)

        concatenators: list[str] = check_config.get("concatenators", CheckSingleValueFields.default_config["concatenators"])
        if not isinstance(concatenators, list) or any(not isinstance(concatenator, str) for concatenator in concatenators):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError("single-value-fields.concatenators configuration must be a list of strings")
        self.concatenators = concatenators
        self.automatic_concatenate = bool(check_config.get("automatic_concatenate", CheckSingleValueFields.default_config["automatic_concatenate"]))

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_FIELDS) for track in album.tracks):
            return None  # this check only makes sense for files with common fields

        multiple_value_fields: list[dict[str, dict[str, Sequence[str]]]] = []
        duplicates = False
        for track in sorted(album.tracks, key=lambda track: track.filename):
            for field in self.single_value_fields:
                # check for multiple values for field
                fields = track.tag_dict()
                if field in fields and len(fields[field]) > 1:
                    multiple_value_fields.append({track.filename: {field: fields[field]}})
                    if len(set(fields[field])) < len(fields[field]):
                        duplicates = True

        if len(multiple_value_fields) > 0:
            option_free_text = False
            options = [OPTION_REMOVE_DUPLICATES_ONLY] if duplicates else []
            for concatenator in self.concatenators:
                options.append(f'{OPTION_CONCATENATE_WITH}"{concatenator}"')
            option_automatic_index = 0 if duplicates or self.automatic_concatenate else None
            return CheckResult(
                f"multiple values for single value fields\n{yaml.dump(multiple_value_fields)}",
                Fixer(
                    lambda option: self._fix(album, option),
                    options,
                    option_free_text,
                    option_automatic_index,
                    (["track", "filename"], [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)]),
                ),
            )

    def _fix(self, album: Album, option: str):
        if option.startswith(OPTION_CONCATENATE_WITH):
            concat = option[len(OPTION_CONCATENATE_WITH) + 1 : -1]
        elif option == OPTION_REMOVE_DUPLICATES_ONLY:
            concat = None
        else:
            raise ValueError(f"invalid option {option}")

        changed = False
        for track in sorted(album.tracks):
            file = self.ctx.config.library / album.path / track.filename
            new_values: list[tuple[BasicField, str | list[str] | None]] = []
            fields = track.tag_dict()
            for field in self.single_value_fields:
                if field in fields and len(fields[field]) > 1:
                    unique_values = list(OrderedDict.fromkeys(fields[field]))
                    if concat:
                        unique_values = [concat.join(unique_values)]
                    new_values.append((field, unique_values))
                    changed = True
            if new_values:
                self.ctx.console.print(f"setting {' and '.join(list(name for (name, _) in new_values))} on {escape(track.filename)}", highlight=False)
                self.tagger.get(album.path).set_basic_fields(file, new_values)
                changed = True

        return FixResult.of(changed)
