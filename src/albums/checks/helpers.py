import re
from collections import defaultdict
from os import unlink
from typing import Collection, Final, List, Mapping, Sequence, Tuple

from rich.markup import escape

from ..app import Context
from ..entities import Album, Track
from ..tagger.types import BasicField
from .check_types import FixResult

FRONT_COVER_FILENAME: Final = "cover"


def album_display_name(ctx: Context, album: Album) -> str:
    return ctx.config.library.name if album.path == "." else escape(album.path + " ").strip()


def get_tracks_by_disc(tracks: Sequence[Track]) -> Mapping[int, List[Track]] | None:
    """
    Return a dict mapping a list of tracks to discnumber values if possible. Tracks with no discnumber are mapped to 0.

    Result will be None if a track has multiple values for tracknumber or discnumber.
    Result will be None if a track has a non-numeric tracknumber or discnumber.
    Result will be None if a track has discnumber 0.
    """
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


def ordered_tracks(album: Album):
    # sort by discnumber/tracknumber field if all tracks have one
    has_discnumber = all(len(track.get(BasicField.DISCNUMBER, default=[])) == 1 for track in album.tracks)
    if all(len(track.get(BasicField.TRACKNUMBER, default=[])) == 1 for track in album.tracks):
        if has_discnumber:
            return sorted(album.tracks, key=lambda t: (t.get(BasicField.DISCNUMBER)[0], t.get(BasicField.TRACKNUMBER)[0]))
        else:
            return sorted(album.tracks, key=lambda t: t.get(BasicField.TRACKNUMBER)[0])
    else:  # default album sort is by filename
        return sorted(album.tracks)


def describe_track_number(track: Track):
    fields = track.field_dict()

    if BasicField.DISCNUMBER in fields or BasicField.DISCTOTAL in fields:
        s = f"(disc {fields.get(BasicField.DISCNUMBER, ['<no disc>'])[0]}{('/' + fields[BasicField.DISCTOTAL][0]) if BasicField.DISCTOTAL in fields else ''}) "
    else:
        s = ""

    s += f"{fields.get(BasicField.TRACKNUMBER, ['<no track>'])[0]}{('/' + fields[BasicField.TRACKTOTAL][0]) if BasicField.TRACKTOTAL in fields else ''}"
    return s


def format_field_values(values: Sequence[str] | None) -> str:
    if values is None:
        return "[bold italic]None[/bold italic]"
    if len(values) == 1:
        return escape(str(values[0]))
    return escape(str(values))


def parse_filename(filename: str) -> Tuple[int | None, int | None, str | None]:
    filename_parser = "(?P<track1>\\d+)?(?:-(?P<track2>\\d+)?)?(?:[\\s\\-]+|\\.\\s+)?(?P<title>.*)(?:\\s+)?\\.\\w+"
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
