from ..types import Album
from .base_check import Check, CheckResult, ProblemCategory


class CheckAlbumUnderAlbum(Check):
    name = "album_under_album"
    default_config = {"enabled": True}

    def check(self, album: Album):
        if not self.ctx.db:
            raise ValueError("CheckAlbumUnderAlbum.check called without a db connection")

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
            return CheckResult(ProblemCategory.FOLDERS, f"there are {matches} albums in directories under album {album.path}")
