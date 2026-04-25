from typing import Final

from .base_check import Check
from .numbering.check_disc_in_track_number import CheckDiscInTrackNumber
from .numbering.check_disc_numbering import CheckDiscNumbering
from .numbering.check_invalid_track_or_disc_number import CheckInvalidTrackOrDiscNumber
from .numbering.check_track_numbering import CheckTrackNumbering
from .numbering.check_zero_pad_numbers import CheckZeroPadNumbers
from .path.check_album_under_album import CheckAlbumUnderAlbum
from .path.check_cover_filename import CheckCoverFilename
from .path.check_duplicate_pathname import CheckDuplicatePathname
from .path.check_file_extension import CheckFileExtension
from .path.check_folder_name import CheckFolderName
from .path.check_illegal_pathname import CheckIllegalPathname
from .path.check_track_filename import CheckTrackFilename
from .picture.check_album_art import CheckAlbumArt
from .picture.check_conflicting_embedded import CheckConflictingEmbedded
from .picture.check_cover_available import CheckCoverAvailable
from .picture.check_cover_dimensions import CheckCoverDimensions
from .picture.check_cover_embedded import CheckCoverEmbedded
from .picture.check_cover_unique import CheckCoverUnique
from .picture.check_duplicate_image import CheckDuplicateImage
from .picture.check_invalid_image import CheckInvalidImage
from .picture.check_picture_metadata import CheckPictureMetadata
from .tags.check_album_artist import CheckAlbumArtist
from .tags.check_album_artist_sort import CheckAlbumArtistSort
from .tags.check_album_sort import CheckAlbumSort
from .tags.check_album_tag import CheckAlbumTag
from .tags.check_artist_tag import CheckArtistTag
from .tags.check_barcode_tag import CheckBarcodeTag
from .tags.check_compilation_tag import CheckCompilationTag
from .tags.check_duplicate_album import CheckDuplicateAlbum
from .tags.check_extra_whitespace import CheckExtraWhitespace
from .tags.check_genre_present import CheckGenrePresent
from .tags.check_musicbrainz_tags import CheckMusicBrainzTags
from .tags.check_publisher_tag import CheckPublisherTag
from .tags.check_single_value_tags import CheckSingleValueTags
from .tags.check_track_title import CheckTrackTitle
from .tags.check_unreadable_track import CheckUnreadableTrack

# enabled checks will run on an album in this order:
ALL_CHECKS: Final[tuple[type[Check], ...]] = (
    # path checks 1
    CheckDuplicatePathname,
    CheckIllegalPathname,
    CheckFileExtension,
    # tag checks 1
    CheckUnreadableTrack,
    CheckExtraWhitespace,
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
    CheckDuplicateAlbum,
    CheckSingleValueTags,
    CheckTrackTitle,
    CheckGenrePresent,
    CheckPublisherTag,
    CheckAlbumSort,
    CheckAlbumArtistSort,
    CheckBarcodeTag,
    CheckCompilationTag,
    CheckMusicBrainzTags,
    # picture checks
    CheckInvalidImage,
    CheckDuplicateImage,
    CheckPictureMetadata,
    CheckAlbumArt,
    CheckCoverAvailable,
    CheckCoverUnique,
    CheckConflictingEmbedded,
    CheckCoverDimensions,
    CheckCoverEmbedded,
    # path checks 2
    CheckFolderName,
    CheckTrackFilename,
    CheckCoverFilename,
    CheckAlbumUnderAlbum,
)

ALL_CHECK_NAMES: Final = frozenset({check.name for check in ALL_CHECKS})
