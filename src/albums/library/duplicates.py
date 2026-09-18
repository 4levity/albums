"""Find duplicate albums (same artist and album name) in the library."""

from collections import defaultdict
from typing import Mapping, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from albums.app import Context
from albums.entities import Album, Track
from albums.tagger import BasicField

from ..utility import get_album_name_from_tracks, get_artist_from_tracks


def _has_field_value(field: BasicField, value: str):
    """Build an EXISTS clause: some value of *field* on the track equals *value* case-insensitively."""
    values = func.json_each(func.json_extract(Track.fields, f"$.{field.value}")).table_valued("value")
    return select(1).select_from(values).where(func.lower(values.c.value) == value).exists()


def album_in_library(ctx: Context, album: Album) -> str | None:
    """Look up an album by artist and album name in the library database; returns its path or ``None``."""
    library_ctx = ctx.parent if ctx.parent is not None else ctx
    album_name = get_album_name_from_tracks(album)
    artist = get_artist_from_tracks(album)
    if album_name and artist:
        name_match = _has_field_value(BasicField.ALBUM, str.lower(album_name))
        artist_match = or_(
            _has_field_value(BasicField.ARTIST, str.lower(artist)),
            _has_field_value(BasicField.ALBUMARTIST, str.lower(artist)),
        )
        with Session(library_ctx.db) as session:
            track = session.execute(select(Track).where(name_match, artist_match)).scalars().first()
            if track is not None and track.album is not None:
                return track.album.path
    return None


def _most_common(counts: Mapping[str, int]) -> str:
    """Return the most common value, breaking ties on the count by value, matching the get_*_from_tracks helpers."""
    return sorted(counts.items(), key=lambda i: (-i[1], i[0]))[0][0]


class DuplicateFinder:
    """Index albums by (artist, album name) so duplicates can be looked up without re-querying the database per album."""

    _duplicates: dict[tuple[str, str], list[int]]

    def start(self, session: Session):
        # the most common artist (ARTIST/ALBUMARTIST) and album (ALBUM) value per album, computed in Python
        # over the tracks' stored fields; the queries load no ORM objects. Lowercasing happens in Python
        # because SQLite's lower() is not Unicode-aware (see LibraryFolder.name_cf).
        artist_counts: defaultdict[int, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
        album_name_counts: defaultdict[int, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
        for album_id, fields in session.execute(select(Track.album_id, Track.fields)).yield_per(1000):
            for artist in fields.get(BasicField.ARTIST, ()):
                artist_counts[album_id][artist] += 1
            for albumartist in fields.get(BasicField.ALBUMARTIST, ()):
                artist_counts[album_id][albumartist] += 1
            for album_name in fields.get(BasicField.ALBUM, ()):
                album_name_counts[album_id][album_name] += 1
        albums: defaultdict[tuple[str, str], list[int]] = defaultdict(list)
        for album_id, _path in session.execute(select(Album.album_id, Album.path).order_by(Album.path)).yield_per(1000):
            artists = artist_counts.get(album_id)
            names = album_name_counts.get(album_id)
            if not artists or not names:
                continue
            albums[(str.lower(_most_common(artists)), str.lower(_most_common(names)))].append(album_id)
        self._duplicates = dict((k, ids) for k, ids in albums.items() if len(ids) > 1)
        return self

    def find(self, album: Album) -> Sequence[int] | None:
        """Return the ids of duplicate albums, or ``None``. Only the first album (by path order) of a duplicate set is considered a duplicate.

        Args:
            album: The album to check.

        Returns:
            The ids of the other albums sharing its artist and name if ``album`` is the first of the set, else ``None``.
        """
        album_name = get_album_name_from_tracks(album)
        artist = get_artist_from_tracks(album)
        if not artist or not album_name:
            return None

        # TODO: try variants (without parenthetical, without articles) and/or match "similar" strings
        ids = self._duplicates.get((str.lower(artist), str.lower(album_name)))

        # only the first album in the list fails the check
        if ids is None or ids[0] != album.album_id:
            return None
        return ids[1:]

    def remove(self, album: Album):
        album_name = get_album_name_from_tracks(album)
        artist = get_artist_from_tracks(album)
        if artist is None or album_name is None or album.album_id is None:
            raise RuntimeError(f'remove: target not fully identified (album="{album_name}", artist="{artist}", album_id={album.album_id})')

        # artist: str, album_name: str, album_id: int
        ids = self._duplicates.get((str.lower(artist), str.lower(album_name)), [])
        if album.album_id in ids:
            ids.remove(album.album_id)
        else:
            raise ValueError(f"error, cannot remove duplicate album {album.album_id} ({artist}/{album_name}) because it was not found")
