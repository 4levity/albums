import logging
from copy import copy
from enum import Enum, auto
from pathlib import Path

import humanize

from ..app import SCANNER_VERSION
from ..types import Album, Picture, PictureType, Track
from .metadata import get_metadata
from .picture import get_picture_metadata

logger = logging.getLogger(__name__)

# TODO: support more image file types
# Currently, can add any extension if format is autodetected by Pillow and ".<FORMAT>" is a file extension supported by mimetypes.guess_type
SUPPORTED_IMAGE_SUFFIXES = [".png", ".jpg", ".jpeg", ".gif"]  # note extension is not used to guess format

MAX_IMAGE_SIZE = 128 * 1024 * 1024  # don't load and scan image files larger than this. 16 MB is the max for ID3v2 and FLAC tags.


class AlbumScanResult(Enum):
    NO_TRACKS = auto()
    NEW = auto()
    UPDATED = auto()
    UNCHANGED = auto()


def scan_folder(
    scan_root: Path, album_relpath: str, track_suffixes: set[str], stored_album: Album | None, reread: bool = False
) -> tuple[Album | None, AlbumScanResult]:
    album_path = scan_root / album_relpath
    logger.debug(f"checking {album_path}")

    track_files: list[Path] = []
    picture_paths: list[Path] = []
    for entry in album_path.iterdir():
        if entry.is_file():
            suffix = str.lower(entry.suffix)
            if suffix in track_suffixes:
                track_files.append(entry)
            elif suffix in SUPPORTED_IMAGE_SUFFIXES:
                picture_paths.append(entry)

    track_files = [entry for entry in album_path.iterdir() if entry.is_file() and str.lower(entry.suffix) in track_suffixes]

    if len(track_files) > 0:
        found_tracks = [Track.from_path(file) for file in sorted(track_files)]

        if stored_album is None:
            _load_track_metadata(scan_root, album_relpath, found_tracks)
            picture_files = _load_picture_files(picture_paths)
            return (Album(album_relpath, found_tracks, [], [], picture_files, None, SCANNER_VERSION), AlbumScanResult.NEW)

        tracks_modified = _track_files_modified(stored_album.tracks, found_tracks)
        missing_metadata = _missing_metadata(stored_album)
        pictures_modified = _picture_files_modified(stored_album.picture_files, picture_paths)
        if reread or tracks_modified or missing_metadata or pictures_modified:
            album = copy(stored_album)
            if reread or tracks_modified or missing_metadata:
                _load_track_metadata(scan_root, album_relpath, found_tracks)
                album.tracks = found_tracks
            if pictures_modified:
                album.picture_files = _load_picture_files(picture_paths)
                # preserve front_cover_source setting
                for filename, picture in stored_album.picture_files.items():
                    if picture.front_cover_source:
                        album.picture_files[filename].front_cover_source = True
                        break
            # TODO if the scan was because of missing metadata but we still don't have metadata, return UNCHANGED instead
            # TODO if option reread=True and there were no changes, return UNCHANGED instead
            return (album, AlbumScanResult.UPDATED)
        return (stored_album, AlbumScanResult.UNCHANGED)
    return (None, AlbumScanResult.NO_TRACKS)


def _load_picture_files(paths: list[Path]) -> dict[str, Picture]:
    picture_files: dict[str, Picture] = {}
    for path in paths:
        picture = _picture_from_path(path)
        if picture:
            picture_files[path.name] = picture
    return picture_files


def _picture_files_modified(picture_files: dict[str, Picture], picture_paths: list[Path]):
    if set(picture_files.keys()) != set(path.name for path in picture_paths):
        return True  # different number of files or different filenames
    for path in picture_paths:
        stored = picture_files[path.name]
        stat = path.stat()
        if stored.file_size != stat.st_size or stored.modify_timestamp != int(stat.st_mtime):
            return True
    return False


def _load_track_metadata(library_root: Path, album_path: str, tracks: list[Track]):
    for track in tracks:
        path = library_root / album_path / track.filename
        file_info = get_metadata(path)
        if file_info is None:
            logger.warning(f"couldn't load metadata for track {path}")
        else:
            (tags, stream_info, pictures) = file_info
            track.tags = tags
            track.stream = stream_info
            track.pictures = pictures


def _track_files_modified(tracks1: list[Track], tracks2: list[Track]):
    if len(tracks1) != len(tracks2):
        return True
    for index, t1 in enumerate(tracks1):
        t2 = tracks2[index]
        if t1.filename != t2.filename or t1.file_size != t2.file_size or t1.modify_timestamp != t2.modify_timestamp:
            return True
    return False


def _missing_metadata(album: Album):
    return any(
        not track.tags
        or not track.stream
        or (not track.pictures and any(name.startswith("apic") for name in track.tags))
        or (len(track.pictures) > 1 and max(pic.embed_ix for pic in track.pictures) == 0)
        # or any(pic.load_issue and "error" in pic.load_issue for pic in track.pictures)
        for track in album.tracks
    )  # or any(pic.load_issue and "error" for pic in album.picture_files.values())


def _picture_from_path(file: Path) -> Picture | None:
    stat = file.stat()
    if stat.st_size > MAX_IMAGE_SIZE:
        logger.warning(
            f"skipping image file {str(file)} because it is {humanize.naturalsize(stat.st_size, binary=True)} (albums max = {humanize.naturalsize(MAX_IMAGE_SIZE, binary=True)})"
        )
        # TODO: record the existence of the large image even if we do not load its metadata, just like we would with a load error
        # Note: recording images that are valid but lack metadata would cause issues with detecting duplicates and assigning cover art
        return None
    with open(file, "rb") as f:
        image_data = f.read()
    picture_type = PictureType.from_filename(file.name)
    picture = get_picture_metadata(image_data, picture_type)  # may or may not load successfully
    picture.modify_timestamp = int(stat.st_mtime)
    return picture
