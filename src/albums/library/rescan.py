"""Decide which aspects of files need re-scanning when an album was scanned by an older scanner version.

Every album is stored with the scanner version that last scanned it (``Album.scanner``). When the
scanner is bumped because the database schema or scan logic changed incompatibly, files scanned by
the older version may be missing or have wrong data for the affected aspects (fields, images or
streams), and those aspects must be re-read from the files on disk.

To bump the scanner version:

1. Increment ``SCANNER_VERSION``.
2. Add an entry to ``_SCANNER_VERSION_CHANGES`` for the new version, listing the ``FileAspect``s
   that changed. Versions without an entry conservatively trigger a full rescan of older albums, so
   forgetting to record a change errs on the safe side.
"""

from typing import Final, Mapping

from albums.entities import OtherFile, PictureFile, Track

from .scanner_types import ALL_FILE_ASPECTS, FileAspect, TargetRescan

# Bumped whenever the database schema or scan logic changes incompatibly.
SCANNER_VERSION: Final = 10

# What each scanner version since v7 changed: the aspects of files scanned by earlier versions
# that must be re-read. (Scanner versions before 7 are assumed to have changed everything.)
_SCANNER_VERSION_CHANGES: Final[Mapping[int, frozenset[FileAspect]]] = {
    7: frozenset({FileAspect.STREAMS}),  # v7 added more stream info (bits per sample)
    8: frozenset({FileAspect.FIELDS}),  # v7 field data is suspect due to orm issues
    9: frozenset({FileAspect.STREAMS}),  # v8 could incorrectly treat video as track after rescan
    10: frozenset({FileAspect.FIELDS}),  # v10 reads several new fields
}


def needs_rescan(scanner: int, file: Track | PictureFile | OtherFile) -> TargetRescan | None:
    """Determine which aspects of ``file`` need re-scanning given the scanner version that last scanned it.

    Callers (the library scanner) invoke this for every stored file of an album whose
    ``Album.scanner`` is older than ``SCANNER_VERSION``, and pass the result to the file scanner so
    only the stale aspects are re-read.

    Args:
        scanner: The scanner version stored on the album (``Album.scanner``) that contains ``file``.
        file: The stored file (``Track``, ``PictureFile`` or ``OtherFile``) to possibly rescan.

    Returns:
        ``None`` if ``file`` was last scanned by the current scanner version, otherwise a
        ``TargetRescan`` for ``file`` whose aspects are the union of the aspects changed by every
        scanner version after ``scanner``. Scanner versions before 7, and any version without an
        entry in ``_SCANNER_VERSION_CHANGES``, conservatively trigger a full rescan.
    """
    if scanner >= SCANNER_VERSION:
        return None
    if scanner < 7:
        return TargetRescan(file, aspects=ALL_FILE_ASPECTS)
    aspects: set[FileAspect] = set()
    for version in range(scanner + 1, SCANNER_VERSION + 1):
        changes = _SCANNER_VERSION_CHANGES.get(version)
        if changes is None:
            return TargetRescan(file, aspects=ALL_FILE_ASPECTS)  # version not recorded, be conservative
        aspects.update(changes)
    return TargetRescan(file, aspects=frozenset(aspects))
