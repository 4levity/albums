from typing import Collection

from rich.markup import escape

from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import BasicTag
from ...types import Album, CheckResult, Fixer
from ..base_check import Check


class CheckExtraWhitespace(Check):
    name = "extra-whitespace"
    default_config = {"enabled": True}

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_TAGS) for track in album.tracks):
            return None  # this check only makes sense for files with common tags
        tags: set[BasicTag] = set()
        filenames: set[str] = set()
        example: str | None = None
        for tag, values, filename in [(k, v, track.filename) for track in album.tracks for k, v in track.tag_dict().items()]:
            if bad_value := next((value for value in values if value.strip() != value), None):
                example = f'{tag.value}="{bad_value}"'
                tags.add(tag)
                filenames.add(filename)
        if tags:
            options = [f">> Strip leading and trailing whitespace in tags: {', '.join(sorted(tags))}"]
            option_automatic_index = 0
            return CheckResult(
                f"Extra whitespace present in {len(filenames)} files in tags: {', '.join(sorted(tags))} - example {example}",
                Fixer(
                    lambda _: self._fix_strip_tags(album, filenames),
                    options,
                    False,
                    option_automatic_index,
                ),
            )

    def _fix_strip_tags(self, album: Album, filenames: Collection[str]) -> bool:
        changed = False
        tagger = self.tagger.get(album.path)
        for track in (track for track in album.tracks if track.filename in filenames):
            with tagger.open(track.filename) as tags:
                for tag, values in track.tag_dict().items():
                    new_values = [v.strip() for v in values]
                    if any(new_values[ix] != v for ix, v in enumerate(values)):
                        self.ctx.console.print(f"Removing whitespace from {tag.value} in {escape(track.filename)}")
                        tags.set_tag(tag, new_values)
                        changed = True
        return changed
