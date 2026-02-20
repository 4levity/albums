from .base_check import Check
from .numbering.check_disc_in_track_number import CheckDiscInTrackNumber
from .numbering.check_disc_numbering import CheckDiscNumbering
from .numbering.check_invalid_track_or_disc_number import CheckInvalidTrackOrDiscNumber
from .numbering.check_track_numbering import CheckTrackNumbering
from .numbering.check_zero_pad_numbers import CheckZeroPadNumbers
from .path.check_album_under_album import CheckAlbumUnderAlbum
from .path.check_bad_pathname import CheckBadPathname
from .path.check_cover_filename import CheckCoverFilename
from .picture.check_album_art import CheckAlbumArt
from .picture.check_cover_dimensions import CheckCoverDimensions
from .picture.check_cover_embedded import CheckCoverEmbedded
from .picture.check_cover_selection import CheckCoverSelection
from .picture.check_duplicate_image import CheckDuplicateImage
from .picture.check_embedded_picture_metadata import CheckEmbeddedPictureMetadata
from .picture.check_invalid_image import CheckInvalidImage
from .tags.check_album_artist import CheckAlbumArtist
from .tags.check_album_tag import CheckAlbumTag
from .tags.check_artist_tag import CheckArtistTag
from .tags.check_required_tags import CheckRequiredTags
from .tags.check_single_value_tags import CheckSingleValueTags
from .tags.check_track_title import CheckTrackTitle

# enabled checks will run on an album in this order:
ALL_CHECKS: tuple[type[Check], ...] = (
    # path checks 1
    CheckBadPathname,
    # numbering checks
    CheckDiscInTrackNumber,
    CheckInvalidTrackOrDiscNumber,
    CheckDiscNumbering,
    CheckTrackNumbering,
    CheckZeroPadNumbers,
    # more tag checks
    CheckAlbumTag,
    CheckAlbumArtist,
    CheckArtistTag,
    CheckRequiredTags,
    CheckSingleValueTags,
    CheckTrackTitle,
    # picture checks
    CheckInvalidImage,
    CheckDuplicateImage,
    CheckEmbeddedPictureMetadata,
    CheckAlbumArt,
    CheckCoverSelection,
    CheckCoverDimensions,
    CheckCoverEmbedded,
    # path checks 2
    CheckCoverFilename,
    CheckAlbumUnderAlbum,
)

ALL_CHECK_NAMES = {check.name for check in ALL_CHECKS}
