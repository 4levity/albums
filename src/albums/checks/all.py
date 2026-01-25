from .. import app
from .base_check import Check
from .check_album_artist import CheckAlbumArtist
from .check_album_tag import CheckAlbumTag
from .check_album_under_album import CheckAlbumUnderAlbum
from .check_required_tags import CheckRequiredTags
from .check_single_value_tags import CheckSingleValueTags
from .check_track_number import CheckTrackNumber


_all_checks: list[type[Check]] = [CheckAlbumTag, CheckAlbumUnderAlbum, CheckAlbumArtist, CheckRequiredTags, CheckSingleValueTags, CheckTrackNumber]

ALL_CHECK_NAMES = [check.name for check in _all_checks]
DEFAULT_CHECKS_CONFIG = dict((check.name, check.default_config) for check in _all_checks)


def run_enabled(ctx: app.Context):
    def enabled(check: type[Check]) -> bool:
        return ctx.config.get("checks", {}).get(check.name, {}).get("enabled", False)

    checks = [check(ctx) for check in _all_checks if enabled(check)]

    for album in ctx.select_albums(True):
        for instance in checks:
            if instance.name not in album.ignore_checks:
                album_result = instance.check(album)
                if album_result:
                    yield (album, album_result)
