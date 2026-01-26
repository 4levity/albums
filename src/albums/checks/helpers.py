from ..types import Track


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
