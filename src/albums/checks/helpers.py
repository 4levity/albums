"""Shared helpers for checks: track ordering and numbering, field value formatting, filename parsing and file deletion."""

import re
from collections import defaultdict
from os import unlink
from typing import Collection, Final, List, Mapping, Sequence, Tuple

from rich.markup import escape

from albums.app import Context
from albums.entities import Album, Track
from albums.tagger import BasicField

from .check_types import FixResult

FRONT_COVER_FILENAME: Final = "cover"


def album_display_name(ctx: Context, album: Album) -> str:
    return ctx.config.library.name if album.path == "." else escape(album.path + " ").strip()


def get_tracks_by_disc(tracks: Sequence[Track]) -> Mapping[int, List[Track]] | None:
    """Group tracks by disc number (tracks without a disc number go to disc 0). Return None if any track has missing, multiple, non-numeric, or zero track/disc numbers."""
    if any(
        not (
            len(track.get(BasicField.TRACKNUMBER, default=["0"])) == 1
            and track.get(BasicField.TRACKNUMBER, default=["0"])[0].isdecimal()
            and len(track.get(BasicField.DISCNUMBER, default=["1"])) == 1
            and track.get(BasicField.DISCNUMBER, default=["1"])[0].isdecimal()
            and int(track.get(BasicField.DISCNUMBER, default=["1"])[0]) > 0
        )
        for track in tracks
    ):
        return None

    tracks_by_disc: defaultdict[int, list[Track]] = defaultdict(list)
    for track in tracks:
        discnumber = int(track.get(BasicField.DISCNUMBER, default=["0"])[0])
        tracks_by_disc[discnumber].append(track)

    for discnumber in tracks_by_disc.keys():
        tracks_by_disc[discnumber].sort(key=lambda track: int(track.get(BasicField.TRACKNUMBER, default=["0"])[0]))

    return tracks_by_disc


def _number_sort_key(value: str) -> Tuple[int, int, str]:
    """Sort key for a track/disc number string: decimal values compare numerically (so 2 < 10), non-decimal values sort after all numbers, lexicographically among themselves."""
    if value.isdecimal():
        return (0, int(value), "")
    return (1, 0, value)


def ordered_tracks(album: Album):
    """Return album tracks in playback order: by disc/track number fields when every track has a track number, falling back to filename sort otherwise. Number fields compare numerically, so albums with ≥10 tracks or discs are ordered 1, 2, ..., 10, ... rather than lexicographically."""
    # sort by discnumber/tracknumber field if all tracks have one
    has_discnumber = all(len(track.get(BasicField.DISCNUMBER, default=[])) == 1 for track in album.tracks)
    if all(len(track.get(BasicField.TRACKNUMBER, default=[])) == 1 for track in album.tracks):
        if has_discnumber:
            return sorted(
                album.tracks, key=lambda t: (_number_sort_key(t.get(BasicField.DISCNUMBER)[0]), _number_sort_key(t.get(BasicField.TRACKNUMBER)[0]))
            )
        else:
            return sorted(album.tracks, key=lambda t: _number_sort_key(t.get(BasicField.TRACKNUMBER)[0]))
    else:  # default album sort is by filename
        return sorted(album.tracks)


def describe_track_number(track: Track):
    """Format a track's disc/track number as a human-readable string, noting missing numbers."""
    fields = track.field_dict()

    if BasicField.DISCNUMBER in fields or BasicField.DISCTOTAL in fields:
        s = f"(disc {fields.get(BasicField.DISCNUMBER, ['<no disc>'])[0]}{('/' + fields[BasicField.DISCTOTAL][0]) if BasicField.DISCTOTAL in fields else ''}) "
    else:
        s = ""

    s += f"{fields.get(BasicField.TRACKNUMBER, ['<no track>'])[0]}{('/' + fields[BasicField.TRACKTOTAL][0]) if BasicField.TRACKTOTAL in fields else ''}"
    return s


def format_field_values(values: Sequence[str] | None) -> str:
    """Format field values for display: ``None`` as "None", a single value as-is, multiple values as a list."""
    if values is None:
        return "[bold italic]None[/bold italic]"
    if len(values) == 1:
        return escape(str(values[0]))
    return escape(str(values))


# a date at the start of a filename: a 4-digit year with an optional month and day, separated by dash, underscore or
# dot, or compact (e.g. 2024, 2024-01, 2024-01-05, 20240105)
_LEADING_DATE_RE: Final = re.compile(r"^(\d{4})(?:[-_.]?(\d{1,2}))?(?:[-_.]?(\d{1,2}))?(?=[\s._-])")


def _strip_leading_date(filename: str) -> str:
    """Remove a leading date (year, optional month, optional day) so it is not mistaken for track or disc numbers; returns the rest of the filename, unchanged if there is no plausible date prefix."""
    match = _LEADING_DATE_RE.match(filename)
    if not match:
        return filename
    year, month, day = match.groups()
    if not (1900 <= int(year) <= 2099 and (month is None or 1 <= int(month) <= 12) and (day is None or 1 <= int(day) <= 31)):
        return filename
    return filename[match.end() :].lstrip()


def parse_filename(filename: str) -> Tuple[int | None, int | None, str | None]:
    """Parse ``disc-track title`` or ``track title`` from a filename; returns (disc, track, title), with missing parts as ``None``.

    Only 1-3 digit numbers are treated as track/disc numbers, and a leading date (e.g. ``2024-01-05`` or
    ``20240105``) is ignored rather than mistaken for numbers, so ``2024-01-05 Live show.mp3`` gives the
    title "Live show".
    """
    filename = _strip_leading_date(filename)
    filename_parser = "(?P<track1>\\d{1,3}(?!\\d))?(?:-(?P<track2>\\d{1,3}(?!\\d))?)?(?:[\\s\\-]+|\\.\\s+)?(?P<title>.*)(?:\\s+)?\\.\\w+"
    match = re.fullmatch(filename_parser, filename)
    if not match:
        return (None, None, None)
    title = str(match.group("title"))

    track1 = match.group("track1")
    track2 = match.group("track2")
    if track1 and track2:
        disc = int(track1)
        track = int(track2)
    elif track1:
        disc = None
        track = int(track1)
    else:
        disc = None
        track = None

    return (disc, track, title if title else None)


def delete_files_except(ctx: Context, keep_filename: str | None, album: Album, filenames: Collection[str]):
    """Delete the given album files from disk except for the kept filename; returns a FixResult for whether anything changed."""
    if keep_filename is not None and keep_filename not in filenames:
        raise ValueError(f"invalid option {keep_filename} is not one of {filenames}")

    changed = False
    for filename in filenames:
        if filename == keep_filename:
            ctx.console.print(f"Keeping {escape(filename)}")
        else:
            ctx.console.print(f"Deleting {escape(filename)}")
            path = ctx.config.library / album.path / filename
            unlink(path)
            changed = True
    return FixResult.of(changed)
