from ..context import AppContext
from .base import Check
from .check_album_under_album import CheckAlbumUnderAlbum
from .check_album_artist import CheckAlbumArtist
from .check_required_tags import CheckRequiredTags
from .check_single_value_tags import CheckSingleValueTags


_all_checks: list[type[Check]] = [CheckAlbumUnderAlbum, CheckAlbumArtist, CheckRequiredTags, CheckSingleValueTags]


def run_enabled(ctx: AppContext):
    def enabled(check: type[Check]):
        return str.lower(ctx.config.get("checks", {}).get(check.name, "false")) != "false"

    checks = [check(ctx) for check in _all_checks if enabled(check)]

    for album in ctx.select_albums(True):
        for instance in checks:
            album_result = instance.check(album)
            if album_result:
                yield (album.path, album_result)
