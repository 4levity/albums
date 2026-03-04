import logging
import mimetypes
from copy import copy
from enum import Enum, auto
from pathlib import Path
from typing import Mapping, Sequence, Tuple

import humanize

from ..app import SCANNER_VERSION
from ..picture.format import SUPPORTED_IMAGE_SUFFIXES
from ..picture.scan import PictureScanner
from ..tagger.folder import AlbumTagger
from ..tagger.types import Picture, PictureType
from ..types import Album, PictureFile, Track

logger = logging.getLogger(__name__)

SUPPORTED_FILE_TYPES = frozenset({".flac", ".mp3", ".m4a", ".wma", ".ogg"})

MAX_IMAGE_SIZE = 128 * 1024 * 1024  # don't load and scan image files larger than this. 16 MB is the max for ID3v2 and FLAC tags.


class AlbumScanResult(Enum):
    NO_TRACKS = auto()
    NEW = auto()
    UPDATED = auto()
    UNCHANGED = auto()


def scan_folder(scan_root: Path, album_relpath: str, stored_album: Album | None, reread: bool = False) -> Tuple[Album | None, AlbumScanResult]:
    album_path = scan_root / album_relpath
    logger.debug(f"checking {album_path}")

    track_files: list[Path] = []
    picture_paths: list[Path] = []
    tagger = AlbumTagger(album_path)
    for entry in album_path.iterdir():
        if entry.is_file():
            suffix = str.lower(entry.suffix)
            if suffix in SUPPORTED_FILE_TYPES:
                track_files.append(entry)
            elif suffix in SUPPORTED_IMAGE_SUFFIXES:
                picture_paths.append(entry)

    if len(track_files) > 0:
        found_tracks = [Track.from_path(file) for file in sorted(track_files)]

        if stored_album is None:
            _load_track_metadata(found_tracks, tagger)
            picture_files = _load_picture_files(picture_paths, tagger.get_picture_scanner())
            return (Album(album_relpath, found_tracks, [], [], picture_files, None, SCANNER_VERSION), AlbumScanResult.NEW)

        tracks_modified = _track_files_modified(stored_album.tracks, found_tracks)
        missing_metadata = _missing_metadata(stored_album)
        pictures_modified = _picture_files_modified(stored_album.picture_files, picture_paths)
        if reread or tracks_modified or missing_metadata or pictures_modified:
            album = copy(stored_album)
            if reread or tracks_modified or missing_metadata:
                _load_track_metadata(found_tracks, tagger)
                album.tracks = found_tracks
            if pictures_modified:
                album.picture_files = _load_picture_files(picture_paths, tagger.get_picture_scanner())
                # preserve cover_source setting
                for filename, picture in stored_album.picture_files.items():
                    if picture.cover_source:
                        if filename in album.picture_files:
                            album.picture_files[filename].cover_source = True
                        break
            # TODO if the scan was because of missing metadata but we still don't have metadata, return UNCHANGED instead
            # TODO if option reread=True and there were no changes, return UNCHANGED instead
            return (album, AlbumScanResult.UPDATED)
        return (stored_album, AlbumScanResult.UNCHANGED)
    return (None, AlbumScanResult.NO_TRACKS)


def _load_picture_files(paths: Sequence[Path], picture_scanner: PictureScanner) -> Mapping[str, PictureFile]:
    picture_files: dict[str, PictureFile] = {}
    for path in paths:
        picture = _picture_from_path(path, picture_scanner)
        if picture:
            picture_files[path.name] = picture
    return picture_files


def _picture_files_modified(picture_files: Mapping[str, PictureFile], picture_paths: Sequence[Path]):
    if set(picture_files.keys()) != set(path.name for path in picture_paths):
        return True  # different number of files or different filenames
    for path in picture_paths:
        stored = picture_files[path.name]
        stat = path.stat()
        if stored.picture.file_info.file_size != stat.st_size or stored.modify_timestamp != int(stat.st_mtime):
            return True
    return False


def _load_track_metadata(tracks: Sequence[Track], tagger: AlbumTagger):
    for track in tracks:
        with tagger.open(track.filename) as tags:
            scan_result = tags.scan()
            track.tags = dict((tag, list(values)) for tag, values in scan_result.tags)
            track.pictures = scan_result.pictures
            track.stream = scan_result.stream


def _track_files_modified(tracks1: Sequence[Track], tracks2: Sequence[Track]):
    if len(tracks1) != len(tracks2):
        return True
    sorted_t1 = sorted(tracks1, key=lambda track: track.filename)
    sorted_t2 = sorted(tracks2, key=lambda track: track.filename)
    for index, t1 in enumerate(sorted_t1):
        t2 = sorted_t2[index]
        if t1.filename != t2.filename or t1.file_size != t2.file_size or t1.modify_timestamp != t2.modify_timestamp:
            return True
    return False


def _missing_metadata(album: Album):
    return any(
        not track.tags or not track.stream
        # or any(pic.load_issue and "error" in pic.load_issue for pic in track.pictures)
        for track in album.tracks
    )  # or any(pic.load_issue and "error" for pic in album.picture_files.values())


def _picture_from_path(file: Path, picture_scanner: PictureScanner) -> PictureFile | None:
    stat = file.stat()
    if stat.st_size > MAX_IMAGE_SIZE:
        logger.warning(
            f"skipping image file {str(file)} because it is {humanize.naturalsize(stat.st_size, binary=True)} (albums max = {humanize.naturalsize(MAX_IMAGE_SIZE, binary=True)})"
        )
        # TODO: record the existence of the large image even if we do not load its metadata, just like we would with a load error
        # Note: recording images that are valid but lack metadata would cause issues with detecting duplicates and assigning cover art
        return None

    expect_mime_type, _ = mimetypes.guess_type(file.name)
    scan_result = picture_scanner.scan(read_binary_file(file), expect_mime_type)
    picture = Picture(scan_result.picture_info, PictureType.from_filename(file.name), "", scan_result.load_issue)
    return PictureFile(picture, int(stat.st_mtime), False)


def read_binary_file(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()
