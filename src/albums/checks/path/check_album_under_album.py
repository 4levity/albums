from sqlalchemy import text

from ...types import Album, CheckResult
from ..base_check import Check
from ..helpers import album_display_name


class CheckAlbumUnderAlbum(Check):
    name = "album-under-album"
    default_config = {"enabled": True}

    def check(self, album: Album):
        path = album.path
        like_path = path.replace("|", "||").replace("%", "|%").replace("_", "|_") + "%"
        conn = self.ctx.db.connect()
        (matches,) = next(
            conn.execute(
                text("SELECT COUNT(*) FROM album WHERE path != :path AND path LIKE :like_path ESCAPE '|';"), {"path": path, "like_path": like_path}
            )
        )
        if matches > 0:
            return CheckResult(f"there are {matches} albums in directories under album {album_display_name(self.ctx, album)}")
