import sqlite3


def check(db: sqlite3.Connection, album: dict, checks_enabled: dict):
    albumartists = {}
    artists = {}
    missing_required_tags = {}
    albumartist_and_band = False

    def enabled(opt):
        return opt in checks_enabled and str(checks_enabled[opt]).upper() != "FALSE"

    for track in sorted(album["tracks"], key=lambda track: track["source_file"]):
        if "artist" in track["tags"]:
            artist = f"{track['tags']['artist']}"  # possibly a list
            artists[artist] = artists.get(artist, 0) + 1

        if "albumartist" in track["tags"] and "Band" in track["tags"]:
            albumartist_and_band = True

        if "albumartist" in track["tags"]:
            albumartists[track["tags"]["albumartist"]] = albumartists.get(track["tags"]["albumartist"], 0) + 1
        elif "Band" in track["tags"]:
            albumartists[track["tags"]["Band"]] = albumartists.get(track["tags"]["Band"], 0) + 1
        else:
            albumartists[""] = albumartists.get("", 0) + 1

        for tag in checks_enabled.get("required_tags", "").split("|"):
            if tag != "" and tag not in track["tags"]:
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
        and (sum(albumartists.values()) - albumartists.get("", 0)) != len(album["tracks"]),
        [{"message": f"multiple artists but no album artist ({list(artists.keys())[:2]} ...)"}],
    )
    issues += filter(
        lambda _: enabled("required_tags") and len(missing_required_tags) > 0,
        [{"message": f"tracks missing required tags ({missing_required_tags}"}],
    )
    if enabled("album_under_album"):
        path = album["path"]
        like_path = path.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        (matches,) = db.execute(
            "SELECT COUNT(*) FROM album WHERE path != ? AND path LIKE ? ESCAPE '\\';",
            (
                path,
                like_path,
            ),
        ).fetchone()
        if matches > 0:
            issues.append({"message": f"there are {matches} albums in directories under album {album['path']}"})

    # todo ["Track", "TrackNumber"]

    return issues
