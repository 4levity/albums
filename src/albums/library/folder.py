from copy import copy
from enum import Enum, auto
import logging
from pathlib import Path

from ..types import Album, Track
from .metadata import get_metadata


logger = logging.getLogger(__name__)


class AlbumScanResult(Enum):
    NO_TRACKS = auto()
    NEW = auto()
    UPDATED = auto()
    UNCHANGED = auto()


def scan_folder(
    scan_root: Path, album_relpath: str, suffixes: set[str], stored_album: Album | None, reread: bool = False
) -> tuple[Album | None, AlbumScanResult]:
    album_path = scan_root / album_relpath
    logger.debug(f"checking {album_path}")

    track_files = [entry for entry in album_path.iterdir() if entry.is_file() and str.lower(entry.suffix) in suffixes]
    if len(track_files) > 0:
        found_tracks = [Track.from_path(file) for file in sorted(track_files)]

        if stored_album is None:
            _load_track_metadata(scan_root, album_relpath, found_tracks)
            return (Album(album_relpath, found_tracks), AlbumScanResult.NEW)
        elif reread or _track_files_modified(stored_album.tracks, found_tracks) or _missing_metadata(stored_album.tracks):
            _load_track_metadata(scan_root, album_relpath, found_tracks)
            album = copy(stored_album)
            album.tracks = found_tracks
            return (album, AlbumScanResult.UPDATED)
        return (stored_album, AlbumScanResult.UNCHANGED)
    return (None, AlbumScanResult.NO_TRACKS)


def _load_track_metadata(library_root: Path, album_path: str, tracks: list[Track]):
    for track in tracks:
        path = library_root / album_path / track.filename
        (tags, stream_info) = get_metadata(path)
        track.tags = tags
        if tags is None:
            logger.warning(f"couldn't read tags for {path}")
        track.stream = stream_info
        if stream_info is None:
            logger.warning(f"couldn't read stream info for {path}")


def _track_files_modified(tracks1: list[Track], tracks2: list[Track]):
    if len(tracks1) != len(tracks2):
        return True
    for index, t1 in enumerate(tracks1):
        t2 = tracks2[index]
        if t1.filename != t2.filename or t1.file_size != t2.file_size or t1.modify_timestamp != t2.modify_timestamp:
            return True
    return False


def _missing_metadata(tracks: list[Track]):
    for track in tracks:
        if not track.tags or not track.stream:
            return True
    return False
