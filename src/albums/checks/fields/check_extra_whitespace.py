from typing import Collection

from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.entities import Album
from albums.tagger import AlbumTagger, BasicField, Cap
from albums.words import plural


class CheckExtraWhitespace(Check):
    name = "extra-whitespace"
    default_config = {"enabled": True}

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_FIELDS) for track in album.tracks):
            return None  # this check only makes sense for files with common fields
        fields: set[BasicField] = set()
        filenames: set[str] = set()
        example: str | None = None
        changed_values: list[tuple[str, BasicField, list[str], list[str]]] = []
        for track in sorted(album.tracks):
            for field, values in track.field_dict().items():
                if any(value.strip() != value for value in values):
                    if bad_value := next((value for value in values if value.strip() != value), None):
                        example = f'{field.value}="{bad_value}"'
                    fields.add(field)
                    filenames.add(track.filename)
                    changed_values.append((track.filename, field, list(values), [value.strip() for value in values]))
        if fields:
            options = [f">> Strip leading and trailing whitespace in fields: {', '.join(sorted(fields))}"]
            option_automatic_index = 0

            # put values in double quotes so the offending leading/trailing whitespace is visible
            def quoted(values: list[str]) -> str:
                return ", ".join(f'"{escape(value)}"' for value in values)

            table = (
                ["filename", "field", "current value", "proposed value"],
                [
                    [escape(filename), field.value, quoted(values), f"[yellow]{quoted(stripped)}[/yellow]"]
                    for filename, field, values, stripped in changed_values
                ],
            )
            return CheckResult(
                f"Extra whitespace present in {plural(filenames, 'file')} in fields: {', '.join(sorted(fields))} - example {example}",
                Fixer(
                    lambda _: self._fix_strip_fields(album, filenames),
                    options,
                    False,
                    option_automatic_index,
                    table,
                ),
            )

    def _fix_strip_fields(self, album: Album, filenames: Collection[str]):
        changed = False
        tagger = self.tagger.get(album.path)
        for track in (track for track in sorted(album.tracks) if track.filename in filenames):
            with tagger.open(track.filename) as fields:
                for field, values in track.field_dict().items():
                    new_values = [v.strip() for v in values]
                    if any(new_values[ix] != v for ix, v in enumerate(values)):
                        self.ctx.console.print(f"Removing whitespace from {field.value} in {escape(track.filename)}")
                        fields.set_field(field, new_values)
                        changed = True
        return FixResult.of(changed)
