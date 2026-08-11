from typing import Final

from .base_check import Check
from .fields.check_album_artist import CheckAlbumArtist
from .fields.check_album_artist_sort import CheckAlbumArtistSort
from .fields.check_album_field import CheckAlbumField
from .fields.check_album_sort import CheckAlbumSort
from .fields.check_artist_tag import CheckArtistTag
from .fields.check_barcode_field import CheckBarcodeField
from .fields.check_compilation_field import CheckCompilationField
from .fields.check_duplicate_album import CheckDuplicateAlbum
from .fields.check_extra_whitespace import CheckExtraWhitespace
from .fields.check_genre_present import CheckGenrePresent
from .fields.check_legacy_tags import CheckLegacyTags
from .fields.check_musicbrainz_tags import CheckMusicBrainzTags
from .fields.check_publisher_field import CheckPublisherField
from .fields.check_releasecountry_field import CheckReleaseCountryField
from .fields.check_releasetype_field import CheckReleaseTypeField
from .fields.check_single_value_tags import CheckSingleValueTags
from .fields.check_track_title import CheckTrackTitle
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
from .path.check_unreadable_track import CheckUnreadableTrack
from .picture.check_album_art import CheckAlbumArt
from .picture.check_conflicting_embedded import CheckConflictingEmbedded
from .picture.check_cover_available import CheckCoverAvailable
from .picture.check_cover_dimensions import CheckCoverDimensions
from .picture.check_cover_embedded import CheckCoverEmbedded
from .picture.check_cover_unique import CheckCoverUnique
from .picture.check_duplicate_image import CheckDuplicateImage
from .picture.check_invalid_image import CheckInvalidImage
from .picture.check_picture_metadata import CheckPictureMetadata

# enabled checks will run on an album in this order:
ALL_CHECKS: Final[tuple[type[Check], ...]] = (
    # path checks 1
    CheckDuplicatePathname,
    CheckIllegalPathname,
    CheckFileExtension,
    CheckUnreadableTrack,
    # tag checks 1
    CheckExtraWhitespace,
    CheckLegacyTags,
    # numbering checks
    CheckDiscInTrackNumber,
    CheckInvalidTrackOrDiscNumber,
    CheckDiscNumbering,
    CheckTrackNumbering,
    CheckZeroPadNumbers,
    # more tag checks
    CheckAlbumField,
    CheckAlbumArtist,
    CheckArtistTag,
    CheckDuplicateAlbum,
    CheckSingleValueTags,
    CheckTrackTitle,
    CheckGenrePresent,
    CheckMusicBrainzTags,
    CheckPublisherField,
    CheckAlbumSort,
    CheckAlbumArtistSort,
    CheckBarcodeField,
    CheckCompilationField,
    CheckReleaseTypeField,
    CheckReleaseCountryField,
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
