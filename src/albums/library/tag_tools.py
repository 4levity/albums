from collections import defaultdict

from albums.entities import Album
from albums.tagger.types import BasicField


def get_artist_from_tracks(album: Album) -> str | None:
    artists: defaultdict[str, int] = defaultdict(int)
    for track in album.tracks:
        for artist in track.get(BasicField.ARTIST, []):
            artists[artist] += 1
        for albumartist in track.get(BasicField.ALBUMARTIST, []):
            artists[albumartist] += 1
    artist_list = sorted(((k, v) for k, v in artists.items()), key=lambda i: i[1], reverse=True)
    return artist_list[0][0] if len(artist_list) else None


def get_album_name_from_tracks(album: Album) -> str | None:
    album_names: defaultdict[str, int] = defaultdict(int)
    for track in album.tracks:
        for album_name in track.get(BasicField.ALBUM, []):
            album_names[album_name] += 1
    album_name_list = sorted(((k, v) for k, v in album_names.items()), key=lambda i: i[1], reverse=True)
    return album_name_list[0][0] if len(album_name_list) else None
