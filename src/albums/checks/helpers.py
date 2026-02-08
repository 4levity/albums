import re
from collections import defaultdict

from rich.markup import escape

from ..types import Album, Track


def get_tracks_by_disc(tracks: list[Track]) -> dict[int, list[Track]] | None:
    """
    Return a dict mapping a list of tracks to discnumber values if possible. Tracks with no discnumber are mapped to 0.

    Result will be None if a track has multiple values for tracknumber or discnumber.
    Result will be None if a track has a non-numeric tracknumber or discnumber.
    Result will be None if a track has discnumber 0.
    """
    if any(
        not (
            len(track.tags.get("tracknumber", ["0"])) == 1
            and track.tags.get("tracknumber", ["0"])[0].isdecimal()
            and len(track.tags.get("discnumber", ["1"])) == 1
            and track.tags.get("discnumber", ["1"])[0].isdecimal()
            and int(track.tags.get("discnumber", ["1"])[0]) > 0
        )
        for track in tracks
    ):
        return None

    tracks_by_disc: defaultdict[int, list[Track]] = defaultdict(list)
    for track in tracks:
        discnumber = int(track.tags.get("discnumber", ["0"])[0])
        tracks_by_disc[discnumber].append(track)

    for discnumber in tracks_by_disc.keys():
        tracks_by_disc[discnumber].sort(key=lambda track: int(track.tags.get("tracknumber", ["0"])[0]))

    return tracks_by_disc


def ordered_tracks(album: Album):
    # sort by discnumber/tracknumber tag if all tracks have one
    has_discnumber = all(len(track.tags.get("discnumber", [])) == 1 for track in album.tracks)
    if all(len(track.tags.get("tracknumber", [])) == 1 for track in album.tracks):
        if has_discnumber:
            return sorted(album.tracks, key=lambda t: (t.tags["discnumber"][0], t.tags["tracknumber"][0]))
        else:
            return sorted(album.tracks, key=lambda t: t.tags["tracknumber"][0])
    else:  # default album sort is by filename
        return album.tracks


def describe_track_number(track: Track):
    tags = track.tags

    if "discnumber" in tags or "disctotal" in tags:
        s = f"(disc {tags.get('discnumber', ['<no disc>'])[0]}{('/' + tags['disctotal'][0]) if 'disctotal' in tags else ''}) "
    else:
        s = ""

    s += f"{tags.get('tracknumber', ['<no track>'])[0]}{('/' + tags['tracktotal'][0]) if 'tracktotal' in tags else ''}"
    return s


def show_tag(tag: list[str] | None) -> str:
    if tag is None:
        return "[bold italic]None[/bold italic]"
    if len(tag) == 1:
        return escape(str(tag[0]))
    return escape(str(tag))


def parse_filename(filename: str) -> tuple[int | None, int | None, str | None]:
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
