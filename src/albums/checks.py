import sqlite3


def check(db: sqlite3.Connection, album: dict, checks_enabled: dict):
    albumartists = {}
    artists = {}
    missing_required_tags = {}
    metadata_warnings = []
    albumartist_and_band = False

    def enabled(opt):
        return opt in checks_enabled and str(checks_enabled[opt]).upper() != "FALSE"

    for track in sorted(album["tracks"], key=lambda track: track["SourceFile"]):
        if "Artist" in track:
            artist = f"{track['Artist']}"  # possibly a list
            artists[artist] = artists.get(artist, 0) + 1

        if "Albumartist" in track and "Band" in track:
            albumartist_and_band = True

        if "Albumartist" in track:
            albumartists[track["Albumartist"]] = albumartists.get(track["Albumartist"], 0) + 1
        elif "Band" in track:
            albumartists[track["Band"]] = albumartists.get(track["Band"], 0) + 1
        else:
            albumartists[""] = albumartists.get("", 0) + 1

        for tag in checks_enabled.get("required_tags", "").split("|"):
            if tag != "" and tag not in track:
                missing_required_tags[tag] = missing_required_tags.get(tag, 0) + 1
        if "Warning" in track and track["Warning"] not in metadata_warnings:
            metadata_warnings.append(track["Warning"])

    issues = []
    issues += filter(lambda _: enabled("albumartist_and_band") and albumartist_and_band, [{"message": "albumartist and band tags both present"}])
    issues += filter(lambda _: enabled("metadata_warnings") and len(metadata_warnings) > 0, [{"message": f"tagger warnings ({metadata_warnings}"}])
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
