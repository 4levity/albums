from albums.types import Album


def remove_file(album: Album, filename: str) -> bool:
    while (to_remove := next((o for o in album.other_files if o.filename == filename), None)) is not None:
        album.other_files.remove(to_remove)
    while (to_remove := next((t for t in album.tracks if t.filename == filename), None)) is not None:
        album.tracks.remove(to_remove)
    removed_cover_source = False
    while (original := next((f for f in album.picture_files if f.filename == filename), None)) is not None:
        removed_cover_source |= original.cover_source
        album.picture_files.remove(original)
    return removed_cover_source
