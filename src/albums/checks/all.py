from .base_check import Check
from .check_album_artist import CheckAlbumArtist
from .check_album_tag import CheckAlbumTag
from .check_album_under_album import CheckAlbumUnderAlbum
from .check_disc_in_track_number import CheckDiscInTrackNumber
from .check_invalid_track_or_disc_number import CheckInvalidTrackOrDiscNumber
from .check_required_tags import CheckRequiredTags
from .check_single_value_tags import CheckSingleValueTags
from .check_track_number import CheckTrackNumber
from .check_zero_pad_numbers import CheckZeroPadNumbers


# enabled checks will run on an album in this order:
ALL_CHECKS: tuple[type[Check], ...] = (
    # lower level cleanup
    CheckDiscInTrackNumber,  # run before CheckInvalidTrackOrDiscNumber which would reject disc-in-tracknumber tags
    CheckInvalidTrackOrDiscNumber,  # handles multiple value tags for track/disc numbers
    # general tag contents
    CheckAlbumTag,
    CheckAlbumArtist,
    CheckRequiredTags,
    CheckSingleValueTags,
    CheckTrackNumber,
    # pickier checks, may require correct tags
    CheckZeroPadNumbers,
    # non-tag related
    CheckAlbumUnderAlbum,
)

ALL_CHECK_NAMES = [check.name for check in ALL_CHECKS]
DEFAULT_CHECKS_CONFIG = dict((check.name, check.default_config) for check in ALL_CHECKS)
