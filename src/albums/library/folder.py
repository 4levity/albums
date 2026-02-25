import logging
from copy import copy
from enum import Enum, auto
from pathlib import Path
from typing import Mapping, Sequence, Tuple

import humanize

from albums.tagger.folder import AlbumTagger
from albums.tagger.picture import PictureScanner

from ..app import SCANNER_VERSION
from ..tagger.types import PictureType
from ..types import Album, Picture, Stream, Track
from .metadata import PROCESSED_ID3_TAGS

# , PictureCache, get_metadata, get_picture_metadata

logger = logging.getLogger(__name__)

SUPPORTED_FILE_TYPES = {".flac", ".mp3", ".m4a", ".wma", ".ogg"}

# TODO: support more image file types
# Currently, can add any extension if format is autodetected by Pillow and ".<FORMAT>" is a file extension supported by mimetypes.guess_type
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif"}  # note extension is not used to guess format

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


def _load_picture_files(paths: Sequence[Path], picture_scanner: PictureScanner) -> Mapping[str, Picture]:
    picture_files: dict[str, Picture] = {}
    for path in paths:
        picture = _picture_from_path(path, picture_scanner)
        if picture:
            picture_files[path.name] = picture
    return picture_files


def _picture_files_modified(picture_files: Mapping[str, Picture], picture_paths: Sequence[Path]):
    if set(picture_files.keys()) != set(path.name for path in picture_paths):
        return True  # different number of files or different filenames
    for path in picture_paths:
        stored = picture_files[path.name]
        stat = path.stat()
        if stored.file_size != stat.st_size or stored.modify_timestamp != int(stat.st_mtime):
            return True
    return False


def _load_track_metadata(tracks: Sequence[Track], tagger: AlbumTagger):
    for track in tracks:
        with tagger.open(track.filename) as tags:
            scan_result = tags.scan()
            track.tags = dict((tag.value, list(values)) for tag, values in scan_result.tags)
            track.pictures = [
                Picture(
                    pic.picture_type,
                    pic.file_info.mime_type,
                    pic.file_info.width,
                    pic.file_info.height,
                    pic.file_info.file_size,
                    pic.file_info.hash,
                    pic.description,
                    dict(pic.load_issue) if pic.load_issue else None,
                    None,
                    embed_ix,
                )
                for embed_ix, pic in enumerate(scan_result.pictures)
            ]
            track.stream = Stream(
                scan_result.stream.length,
                scan_result.stream.bitrate,
                scan_result.stream.channels,
                scan_result.stream.codec,
                scan_result.stream.sample_rate,
            )


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
        not track.tags
        or not track.stream
        or any(name.startswith("apic") for name in track.tags)
        or (len(track.pictures) > 1 and max(pic.embed_ix for pic in track.pictures) == 0)
        or any(tag in track.tags for tag in PROCESSED_ID3_TAGS)  # rescan to remove redundant values
        # or any(pic.load_issue and "error" in pic.load_issue for pic in track.pictures)
        for track in album.tracks
    )  # or any(pic.load_issue and "error" for pic in album.picture_files.values())


def _picture_from_path(file: Path, picture_scanner: PictureScanner) -> Picture | None:
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
    scan_result = picture_scanner.scan(image_data)
    picture_type = PictureType.from_filename(file.name)
    picture = Picture(
        picture_type,
        scan_result.picture_info.mime_type,
        scan_result.picture_info.width,
        scan_result.picture_info.height,
        scan_result.picture_info.file_size,
        scan_result.picture_info.hash,
        "",
        dict(scan_result.load_issue) if scan_result.load_issue else None,
        int(stat.st_mtime),
    )
    return picture
