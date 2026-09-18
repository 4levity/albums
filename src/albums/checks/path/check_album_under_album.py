from sqlalchemy import func, select

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult
from albums.checks.helpers import album_display_name
from albums.entities import Album
from albums.words import a_plural, count_phrase


class CheckAlbumUnderAlbum(Check):
    name = "album-under-album"
    default_config = {"enabled": True}

    def check(self, album: Album):
        # Count albums whose path starts with this one. Album paths end in the platform path
        # separator, and no byte falls between a byte and its successor, so raising the last
        # byte by one bounds the range to exactly the paths starting with this one; this
        # case-sensitive range uses the album path index, unlike a case-insensitive LIKE prefix,
        # which scans the whole table for every album.
        path = album.path
        (matches,) = (
            self.session.execute(select(func.count("*")).select_from(Album).where(Album.path > path, Album.path < path[:-1] + chr(ord(path[-1]) + 1)))
            .tuples()
            .one()
        )

        if matches > 0:
            return CheckResult(
                f"there {count_phrase(matches, 'album')} in {a_plural(matches, 'directory')} under album {album_display_name(self.ctx, album)}"
            )
