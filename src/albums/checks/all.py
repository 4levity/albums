from .base_check import Check
from .check_album_art import CheckAlbumArt
from .check_album_artist import CheckAlbumArtist
from .check_album_tag import CheckAlbumTag
from .check_album_under_album import CheckAlbumUnderAlbum
from .check_artist_tag import CheckArtistTag
from .check_disc_in_track_number import CheckDiscInTrackNumber
from .check_disc_numbering import CheckDiscNumbering
from .check_duplicate_images import CheckDuplicateImages
from .check_flac_picture_metadata import CheckFlacPictureMetadata
from .check_front_cover_selection import CheckFrontCoverSelection
from .check_invalid_track_or_disc_number import CheckInvalidTrackOrDiscNumber
from .check_required_tags import CheckRequiredTags
from .check_single_value_tags import CheckSingleValueTags
from .check_track_numbering import CheckTrackNumbering
from .check_track_title import CheckTrackTitle
from .check_zero_pad_numbers import CheckZeroPadNumbers

# enabled checks will run on an album in this order:
ALL_CHECKS: tuple[type[Check], ...] = (
    # lower level cleanup
    CheckDiscInTrackNumber,  # run before CheckInvalidTrackOrDiscNumber which would reject disc-in-tracknumber tags
    CheckInvalidTrackOrDiscNumber,  # handles multiple value tags for track/disc numbers
    # general tag contents
    CheckAlbumTag,
    CheckAlbumArtist,
    CheckArtistTag,
    CheckRequiredTags,
    CheckSingleValueTags,
    CheckDiscNumbering,
    CheckTrackNumbering,
    CheckTrackTitle,
    CheckDuplicateImages,
    CheckFlacPictureMetadata,
    CheckAlbumArt,
    CheckFrontCoverSelection,
    # pickier checks, may require correct tags
    CheckZeroPadNumbers,
    # non-tag related
    CheckAlbumUnderAlbum,
)

ALL_CHECK_NAMES = [check.name for check in ALL_CHECKS]
DEFAULT_CHECK_CONFIGS = dict((check.name, check.default_config) for check in ALL_CHECKS)
