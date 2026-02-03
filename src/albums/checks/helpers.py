from enum import Enum, auto
from rich.markup import escape

from ..types import Album, Track


class ItemTotalPolicy(Enum):
    CONSISTENT = auto()
    ALWAYS = auto()
    NEVER = auto()

    @classmethod
    def from_str(cls, selection: str):
        for policy in cls:
            if str.lower(policy.name) == str.lower(selection):
                return policy
        raise ValueError(f'invalid ItemTotalPolicy "{selection}"')


OPTION_APPLY_POLICY = ">> Apply policy"


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

    tracks_by_disc: dict[int, list[Track]] = {}
    for track in tracks:
        discnumber = int(track.tags.get("discnumber", ["0"])[0])
        if discnumber not in tracks_by_disc:
            tracks_by_disc[discnumber] = []
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
