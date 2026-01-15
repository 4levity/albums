import sqlite3
from ..types import Album


ALL_CHECKS_DEFAULT = {
    "album_under_album": "true",
    "albumartist_and_band": "true",
    "multiple_albumartist_band": "true",
    "needs_albumartist_band": "true",
    "required_tags": "artist|title",
}


def check(db: sqlite3.Connection, album: Album, check_config: dict):
    albumartists = {}
    artists = {}
    missing_required_tags = {}
    albumartist_and_band = False

    def enabled(opt):
        return opt in check_config and str(check_config[opt]).upper() != "FALSE"

    for track in sorted(album.tracks, key=lambda track: track.filename):
        if "artist" in track.tags:
            for artist in track.tags["artist"]:
                artists[artist] = artists.get(artist, 0) + 1

        if "albumartist" in track.tags and "Band" in track.tags:
            albumartist_and_band = True

        if "albumartist" in track.tags:
            for albumartist in track.tags["albumartist"]:
                albumartists[albumartist] = albumartists.get(albumartist, 0) + 1
        elif "band" in track.tags:
            for band in track.tags["band"]:
                albumartists[band] = albumartists.get(track.tags["band"], 0) + 1
        else:
            albumartists[""] = albumartists.get("", 0) + 1

        for tag in check_config.get("required_tags", "").split("|"):
            if tag != "" and tag not in track.tags:
                missing_required_tags[tag] = missing_required_tags.get(tag, 0) + 1

    issues = []
    issues += filter(lambda _: enabled("albumartist_and_band") and albumartist_and_band, [{"message": "albumartist and band tags both present"}])
    issues += filter(
        lambda _: enabled("multiple_albumartist_band") and len(albumartists) > 1,
        [{"message": f"multiple album artist values ({list(albumartists.keys())[:2]} ...)"}],
    )
    issues += filter(
        lambda _: enabled("needs_albumartist_band")
        and len(artists) > 1
        and (sum(albumartists.values()) - albumartists.get("", 0)) != len(album.tracks),
        [{"message": f"multiple artists but no album artist ({list(artists.keys())[:2]} ...)"}],
    )
    issues += filter(
        lambda _: enabled("required_tags") and len(missing_required_tags) > 0,
        [{"message": f"tracks missing required tags {missing_required_tags}"}],
    )
    if enabled("album_under_album"):
        path = album.path
        like_path = path.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        (matches,) = db.execute(
            "SELECT COUNT(*) FROM album WHERE path != ? AND path LIKE ? ESCAPE '\\';",
            (
                path,
                like_path,
            ),
        ).fetchone()
        if matches > 0:
            issues.append({"message": f"there are {matches} albums in directories under album {album.path}"})

    # todo ["Track", "TrackNumber"]

    return issues
