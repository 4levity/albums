from .base_check import Check
from .check_album_artist import CheckAlbumArtist
from .check_album_tag import CheckAlbumTag
from .check_album_under_album import CheckAlbumUnderAlbum
from .check_required_tags import CheckRequiredTags
from .check_single_value_tags import CheckSingleValueTags
from .check_track_number import CheckTrackNumber
from .check_zero_pad_numbers import CheckZeroPadNumbers


ALL_CHECKS: tuple[type[Check], ...] = (
    CheckAlbumTag,
    CheckAlbumUnderAlbum,
    CheckAlbumArtist,
    CheckRequiredTags,
    CheckSingleValueTags,
    CheckTrackNumber,
    CheckZeroPadNumbers,
)

ALL_CHECK_NAMES = [check.name for check in ALL_CHECKS]
DEFAULT_CHECKS_CONFIG = dict((check.name, check.default_config) for check in ALL_CHECKS)
