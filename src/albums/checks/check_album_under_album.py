from ..types import Album
from .base_check import Check, CheckResult


class CheckAlbumUnderAlbum(Check):
    name = "album_under_album"
    default_config = "true"

    def check(self, album: Album):
        path = album.path
        like_path = path.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        (matches,) = self.ctx.db.execute(
            "SELECT COUNT(*) FROM album WHERE path != ? AND path LIKE ? ESCAPE '\\';",
            (
                path,
                like_path,
            ),
        ).fetchone()
        if matches > 0:
            return CheckResult(self.name, f"there are {matches} albums in directories under album {album.path}")
