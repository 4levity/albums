"""Base class for checks of sort-order fields (albumsort, albumartistsort, artistsort).

The value of a sort-order field is generated, on each track, from the value(s) of a
source field (album, albumartist or artist): the values are concatenated with
`SORT_VALUE_SEPARATOR` and a leading article is moved to the end, e.g. "The
Beatles" -> "Beatles, The". Consistency of the source field per album is the
job of the check for the
source field (which the sort check requires to pass first), so the generated sort
values are the same per album for albumsort and albumartistsort.

A track without a source value has no sort value to generate, so the sort field must
not be present on it, and any other value is considered incorrect. A user who wants
to keep a manually chosen sort value should ignore this check for the album - there
is no option to keep an alternative value.
"""

from typing import Any, Final, Mapping, Sequence

from rich.markup import escape

from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField, Cap
from albums.words import move_leading_article

from .base_check import Check
from .check_types import CheckResult, Fixer, FixResult
from .field_policy import Policy
from .helpers import describe_track_number, ordered_tracks

# The generated value can be different on each track (e.g. for artistsort), so it can't
# always be shown as a plain option; the fix sets the generated value on each track
OPTION_GENERATED_VALUE: Final = ">> Set generated value on all tracks"

# Separator used to concatenate multiple values of a field when generating a sort value,
# e.g. the artistsort of a track with artists "The Beatles" and "Wings" is "Beatles, The / Wings"
SORT_VALUE_SEPARATOR: Final = " / "


def make_sort_value(values: Sequence[str], separator: str = SORT_VALUE_SEPARATOR) -> str:
    """Generate a sort-order value from the value(s) of a field: concatenate the values with the separator, after moving leading articles to the end."""
    return separator.join(move_leading_article(value) for value in values)


class BaseCheckSortField(Check):
    """Check a sort-order field generated from a source field, applying a presence policy.

    Subclasses must define ``name``, the sort ``field`` to check and the ``source_field``
    to generate from, the ``field_description``, and ``must_pass_checks`` (the check for
    the source field, which guarantees it is a single consistent value per album).
    """

    name: str
    field: BasicField
    source_field: BasicField
    field_description: str = ""

    default_config = {"enabled": True, "presence": "consistent"}

    def init(self, check_config: dict[str, Any]):
        self.presence = Policy.from_str(str(check_config.get("presence", self.default_config["presence"])))
        if not self.field_description:
            self.field_description = self.field.value
        self.option_remove_field = f">> Remove {self.field_description} from all tracks"

    def check(self, album: Album) -> CheckResult | None:
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_FIELDS) for track in album.tracks):
            return None

        source_by_track = {track.filename: tuple(value for value in track.get(self.source_field, default=[]) if value) for track in album.tracks}
        generated_by_track = {filename: (make_sort_value(values) if values else None) for filename, values in source_by_track.items()}
        can_generate_all = all(value is not None for value in generated_by_track.values())
        present = [track for track in album.tracks if self._values(track) is not None]

        if self.presence == Policy.NEVER:
            if present:
                return CheckResult(f"{self.field.value} policy=NEVER but it appears on tracks", self._make_fixer_remove(album))
            return None

        if self.presence == Policy.ALWAYS:
            if not can_generate_all:
                # the policy can't be satisfied: every track should have the sort field, but some have no source value to generate it from
                return CheckResult(f"{self.field.value} policy=ALWAYS but {self.source_field.value} is not on all tracks", None)
            if self._wrong_tracks(album.tracks, generated_by_track):
                return CheckResult(
                    f"{self.field.value} policy=ALWAYS but it is not set to the generated value on all tracks",
                    self._make_fixer(album, generated_by_track),
                )
            return None

        # policy CONSISTENT: the field should be on all tracks (set to the generated value), or on none
        if not present:
            if can_generate_all and any(
                generated_by_track[filename] != SORT_VALUE_SEPARATOR.join(source_by_track[filename]) for filename in source_by_track
            ):
                # no track has the field, but the generated value is different from the source value (e.g. a leading article), so it should be set
                return CheckResult(
                    f"{self.field_description} is not set but it should be, because the generated value is different from {self.source_field.value}",
                    self._make_fixer(album, generated_by_track),
                )
            return None
        if len(present) != len(album.tracks):
            if can_generate_all:
                return CheckResult(
                    f"{self.field.value} policy=CONSISTENT but it is on some tracks and not others", self._make_fixer(album, generated_by_track)
                )
            # the value can't be generated for every track, so the field can't be set on all of them; the only consistent state is that it is on none
            return CheckResult(
                f"{self.field.value} policy=CONSISTENT but it can't be set on all tracks because {self.source_field.value} is not on all tracks, so it must be removed",
                self._make_fixer_remove(album),
            )
        wrong = self._wrong_tracks(album.tracks, generated_by_track)
        if wrong:
            if can_generate_all:
                return CheckResult(
                    f"incorrect {self.field_description} on {len(wrong)} track{'s' if len(wrong) > 1 else ''}",
                    self._make_fixer(album, generated_by_track),
                )
            # the field is present on a track without a source value, so it can't be correct there and must be removed
            return CheckResult(f"{self.field.value} appears on tracks without {self.source_field.value}", self._make_fixer_remove(album))
        return None

    def _wrong_tracks(self, tracks: list[Track], generated_by_track: Mapping[str, str | None]) -> list[Track]:
        """Tracks whose sort field is not the generated value (a track without a generated value should have no sort field)."""
        return [track for track in tracks if self._values(track) != (generated_by_track[track.filename],)]

    def _values(self, track: Track) -> tuple[str, ...] | None:
        """The track's sort field values, or None if the field is (effectively) not present."""
        values = tuple(value for value in track.get(self.field, default=[]) if value)
        return values if values else None

    def _make_fixer(self, album: Album, generated_by_track: Mapping[str, str | None]) -> Fixer:
        return Fixer(
            lambda option: self._fix(album, option, generated_by_track),
            [OPTION_GENERATED_VALUE, self.option_remove_field],
            option_free_text=False,
            option_automatic_index=0,
            table=self._make_table(album, generated_by_track),
            prompt=f"Select {self.field_description} for all tracks",
        )

    def _make_fixer_remove(self, album: Album) -> Fixer:
        return Fixer(
            lambda option: self._fix_remove(album),
            [self.option_remove_field],
            option_free_text=False,
            option_automatic_index=0,
            table=self._make_table(album, {}),
            prompt=f"Remove {self.field_description} from all tracks",
        )

    def _fix(self, album: Album, option: str, generated_by_track: Mapping[str, str | None]) -> FixResult:
        tagger = self.tagger.get(album.path)
        changed = False
        for track in sorted(album.tracks):
            current = self._values(track)
            if option == self.option_remove_field:
                if current is not None:
                    self._remove(tagger, track)
                    changed = True
                continue
            expected = generated_by_track[track.filename]
            if expected is None:
                if current is not None:
                    self._remove(tagger, track)
                    changed = True
            elif current != (expected,):
                self._set(tagger, track, expected)
                changed = True
        return FixResult.of(changed)

    def _fix_remove(self, album: Album) -> FixResult:
        tagger = self.tagger.get(album.path)
        changed = False
        for track in sorted(album.tracks):
            if self._values(track) is not None:
                self._remove(tagger, track)
                changed = True
        return FixResult.of(changed)

    def _set(self, tagger: AlbumTagger, track: Track, value: str) -> None:
        self.ctx.console.print(f"Setting {self.field_description} to {escape(value)} on {escape(track.filename)}", highlight=False)
        with tagger.open(track.filename) as tag:
            tag.set_field(self.field, value)

    def _remove(self, tagger: AlbumTagger, track: Track) -> None:
        self.ctx.console.print(f"Removing {self.field_description} on {escape(track.filename)}", highlight=False)
        with tagger.open(track.filename) as tag:
            tag.set_field(self.field, None)

    def _make_table(self, album: Album, generated_by_track: Mapping[str, str | None]) -> tuple[list[str], list[list[str]]]:
        rows: list[list[str]] = []
        for track in ordered_tracks(album):
            source_values = tuple(value for value in track.get(self.source_field, default=[]) if value)
            current = self._values(track)
            proposed = generated_by_track.get(track.filename)
            rows.append(
                [
                    describe_track_number(track),
                    escape(track.filename),
                    escape(", ".join(source_values)) if source_values else "[italic]none[/italic]",
                    escape(", ".join(current)) if current else "[italic]none[/italic]",
                    escape(proposed) if proposed else "[italic]none[/italic]",
                ]
            )
        return (["track", "filename", self.source_field.value, self.field.value, "proposed value"], rows)
