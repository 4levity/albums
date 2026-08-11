from sqlalchemy import and_, func, select

from ...entities import Album
from ...words.make import a_plural, is_plural
from ..base_check import Check
from ..check_types import CheckResult
from ..helpers import album_display_name


class CheckAlbumUnderAlbum(Check):
    name = "album-under-album"
    default_config = {"enabled": True}

    def check(self, album: Album):
        path = album.path
        like_path = path.replace("|", "||").replace("%", "|%").replace("_", "|_") + "%"
        (matches,) = (
            self.session.execute(select(func.count("*")).select_from(Album).filter(and_(Album.path != path, Album.path.like(like_path, "|"))))
            .tuples()
            .one()
        )

        if matches > 0:
            return CheckResult(
                f"there {is_plural(matches, 'album')} in {a_plural(matches, 'directory')} under album {album_display_name(self.ctx, album)}"
            )
