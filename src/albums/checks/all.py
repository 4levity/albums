from typing import Final, Iterable

from .base_check import Check
from .fields.check_album import CheckAlbumField
from .fields.check_album_artist import CheckAlbumArtist
from .fields.check_album_artist_sort import CheckAlbumArtistSort
from .fields.check_album_sort import CheckAlbumSort
from .fields.check_artist import CheckArtistField
from .fields.check_artist_sort import CheckArtistSort
from .fields.check_barcode import CheckBarcodeField
from .fields.check_compilation import CheckCompilationField
from .fields.check_duplicate_album import CheckDuplicateAlbum
from .fields.check_extra_whitespace import CheckExtraWhitespace
from .fields.check_genre_present import CheckGenrePresent
from .fields.check_legacy_fields import CheckLegacyFields
from .fields.check_musicbrainz_fields import CheckMusicBrainzFields
from .fields.check_publisher import CheckPublisherField
from .fields.check_releasecountry import CheckReleaseCountryField
from .fields.check_releasedate import CheckReleaseDateField
from .fields.check_releasetype import CheckReleaseTypeField
from .fields.check_single_value_fields import CheckSingleValueFields
from .fields.check_track_title import CheckTrackTitle
from .numbering.check_disc_in_track_number import CheckDiscInTrackNumber
from .numbering.check_disc_numbering import CheckDiscNumbering
from .numbering.check_invalid_track_or_disc_number import CheckInvalidTrackOrDiscNumber
from .numbering.check_track_numbering import CheckTrackNumbering
from .numbering.check_zero_pad_numbers import CheckZeroPadNumbers
from .path.check_album_under_album import CheckAlbumUnderAlbum
from .path.check_cover_filename import CheckCoverFilename
from .path.check_duplicate_filename import CheckDuplicateFilename
from .path.check_duplicate_folder_name import CheckDuplicateFolderName
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
    CheckDuplicateFilename,
    CheckDuplicateFolderName,
    CheckIllegalPathname,
    CheckFileExtension,
    CheckUnreadableTrack,
    # field checks 1
    CheckExtraWhitespace,
    CheckLegacyFields,
    # numbering checks
    CheckDiscInTrackNumber,
    CheckInvalidTrackOrDiscNumber,
    CheckDiscNumbering,
    CheckTrackNumbering,
    CheckZeroPadNumbers,
    # more field checks
    CheckAlbumField,
    CheckAlbumArtist,
    CheckArtistField,
    CheckDuplicateAlbum,
    CheckSingleValueFields,
    CheckTrackTitle,
    CheckGenrePresent,
    CheckMusicBrainzFields,
    CheckPublisherField,
    CheckAlbumSort,
    CheckAlbumArtistSort,
    CheckArtistSort,
    CheckBarcodeField,
    CheckCompilationField,
    CheckReleaseTypeField,
    CheckReleaseCountryField,
    CheckReleaseDateField,
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

ALL_CHECK_NAMES: Final = frozenset(check.name for check in ALL_CHECKS)


def _check_dependency_graphs() -> tuple[dict[str, frozenset[str]], dict[str, frozenset[str]]]:
    """Build the check dependency graph from each check's must_pass_checks: check name -> the checks it
    depends on and the checks that depend on it."""
    dependencies: dict[str, set[str]] = {}
    dependents: dict[str, set[str]] = {}
    for check in ALL_CHECKS:
        dependencies.setdefault(check.name, set()).update(check.must_pass_checks)
        for dep in check.must_pass_checks:
            dependents.setdefault(dep, set()).add(check.name)
    return ({name: frozenset(deps) for name, deps in dependencies.items()}, {name: frozenset(deps) for name, deps in dependents.items()})


CHECK_DEPENDENCIES, CHECK_DEPENDENTS = _check_dependency_graphs()


def transitive_dependencies(check_name: str) -> set[str]:
    """Return the check names that ``check_name`` directly or transitively depends on (its must_pass_checks, recursively)."""
    dependencies: set[str] = set()
    stack = [check_name]
    while stack:
        for dep in CHECK_DEPENDENCIES.get(stack.pop(), frozenset()):
            if dep not in dependencies:
                dependencies.add(dep)
                stack.append(dep)
    return dependencies


def transitive_dependents(check_name: str) -> set[str]:
    """Return the check names that directly or transitively depend on ``check_name`` (they run after it in ALL_CHECKS order)."""
    dependents: set[str] = set()
    stack = [check_name]
    while stack:
        for dependent in CHECK_DEPENDENTS.get(stack.pop(), frozenset()):
            if dependent not in dependents:
                dependents.add(dependent)
                stack.append(dependent)
    return dependents


def implicitly_ignored_checks(ignored_checks: Iterable[str]) -> set[str]:
    """Return the check names implicitly ignored for an album with the given ignored checks.

    An ignored check never passes, so every check that depends on it, directly or transitively, cannot run
    and is ignored implicitly, without additional configuration.
    """
    implicitly_ignored: set[str] = set()
    for ignored_check in ignored_checks:
        implicitly_ignored |= transitive_dependents(ignored_check)
    return implicitly_ignored


def check_run_order(check_names: Iterable[str]) -> list[str]:
    """Return the given check names in the order the checks would run (their order in ALL_CHECKS)."""
    position = {check.name: i for i, check in enumerate(ALL_CHECKS)}
    return sorted(check_names, key=lambda name: position[name])
