"""Find duplicate albums (same artist and album name) in the library."""

from collections import defaultdict
from typing import Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from albums.app import Context
from albums.entities import Album, FieldV
from albums.tagger import BasicField

from ..utility import get_album_name_from_tracks, get_artist_from_tracks


def album_in_library(ctx: Context, album: Album) -> str | None:
    """Look up an album by artist and album name in the library database; returns its path or ``None``."""
    library_ctx = ctx.parent if ctx.parent is not None else ctx
    album_name = get_album_name_from_tracks(album)
    artist = get_artist_from_tracks(album)
    if album_name and artist:
        with Session(library_ctx.db) as session:
            FieldV2 = aliased(FieldV)
            stmt = (
                select(FieldV)
                .filter(and_(FieldV.field == BasicField.ALBUM, func.lower(FieldV.value) == str.lower(album_name)))
                .join(
                    FieldV2,
                    and_(
                        FieldV.track_id == FieldV2.track_id,
                        func.lower(FieldV2.value) == str.lower(artist),
                        or_(FieldV2.field == BasicField.ARTIST, FieldV2.field == BasicField.ALBUMARTIST),
                    ),
                )
            )
            tag_match = session.execute(stmt).tuples().first()
            if tag_match is not None and tag_match[0].track and tag_match[0].track.album:
                return tag_match[0].track.album.path
    return None


class DuplicateFinder:
    """Index albums by (artist, album name) so duplicates can be looked up without re-querying the database per album."""

    _duplicates: dict[tuple[str, str], list[int]] = {}

    def start(self, session: Session):  # TODO make initializing DuplicateFinder faster
        # this takes several seconds on a large library, but when checking the whole library, this way is 6x faster than querying per album
        albums: defaultdict[tuple[str, str], list[int]] = defaultdict(list[int])
        for (album,) in session.execute(select(Album).order_by(Album.path)).tuples():
            add_album_name = get_album_name_from_tracks(album)
            add_artist = get_artist_from_tracks(album)
            if add_album_name and add_artist and album.album_id is not None:
                albums[(str.lower(add_artist), str.lower(add_album_name))].append(album.album_id)
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
