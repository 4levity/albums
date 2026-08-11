import io
import os
import shutil
from pathlib import Path
from typing import Collection, Mapping, Set

from PIL import Image

from albums.entities import Album, Track, TrackPicture
from albums.picture.format import mime_type_to_format
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import BasicTag, Picture
from albums.tagger.vorbis import LEGACY_VORBIS_TAGS

from .empty_files import (
    EMPTY_AIFF_FILE_BYTES,
    EMPTY_FLAC_FILE_BYTES,
    EMPTY_M4A_FILE_BYTES,
    EMPTY_MP3_FILE_BYTES,
    EMPTY_MP4_VIDEO_FILE_BYTES,
    EMPTY_OGG_VORBIS_FILE_BYTES,
    EMPTY_WMA_FILE_BYTES,
)

LEGACY_TAG_MAP: Mapping[str, BasicTag] = dict(LEGACY_VORBIS_TAGS)

test_data_path = Path(__file__).resolve().parent / "libraries"


def create_track_file(path: Path, spec: Track):
    filename: Path = path / spec.filename
    with open(filename, "wb") as file:
        if filename.suffix == ".flac":
            file.write(EMPTY_FLAC_FILE_BYTES)
        elif filename.suffix in {".m4a", ".m4b", ".mp4"}:
            file.write(EMPTY_M4A_FILE_BYTES)
        elif filename.suffix == ".mp3":
            file.write(EMPTY_MP3_FILE_BYTES)
        elif filename.suffix == ".wma":
            file.write(EMPTY_WMA_FILE_BYTES)
        elif filename.suffix == ".ogg":
            file.write(EMPTY_OGG_VORBIS_FILE_BYTES)
        elif filename.suffix == ".aiff":
            file.write(EMPTY_AIFF_FILE_BYTES)
    if spec.tags or spec.pictures:
        tagger = AlbumTagger(path, padding=lambda _: 0)
        with tagger.open(spec.filename) as tags:
            for pic in spec.pictures:
                image_data = make_image_data(pic.picture_info.width, pic.picture_info.height, mime_type_to_format(pic.picture_info.mime_type))
                picture = Picture(pic.picture_info, pic.picture_type, pic.description) if isinstance(pic, TrackPicture) else pic
                tags.add_picture(picture, image_data)
            spec_tags = spec.tag_dict()
            represented_by_legacy_tags: Set[BasicTag] = set()
            for tag_name in spec.legacy_tags:
                basic_tag = LEGACY_TAG_MAP[tag_name]
                tags.set_tag(tag_name, spec_tags[basic_tag])
                represented_by_legacy_tags.add(basic_tag)
            for tag_name, values in spec_tags.items():
                if tag_name not in represented_by_legacy_tags:
                    tags.set_tag(tag_name, list(values))


def create_picture_file(path: Path, width: int = 400, height: int = 400, color: str = "blue"):
    image = Image.new("RGB", (width, height), color="blue")
    image.save(path)


def create_other_file(path: Path):
    with open(path, "wb") as file:
        if path.suffix == ".mp4":
            file.write(EMPTY_MP4_VIDEO_FILE_BYTES)


def create_album_in_library(library_path: Path, album: Album):
    path = library_path / album.path
    os.makedirs(path)
    for track in album.tracks:
        create_track_file(path, track)
    for file in album.picture_files:
        create_picture_file(path / file.filename, file.picture_info.width, file.picture_info.height)
    for other in album.other_files:
        create_other_file(path / other.filename)


def create_library(library_name: str, albums: Collection[Album]):
    library_path = test_data_path / library_name
    shutil.rmtree(library_path, ignore_errors=True)
    os.makedirs(library_path)
    for album in albums:
        create_album_in_library(library_path, album)
    return library_path


def make_image_data(width: int = 400, height: int = 400, format: str = "PNG", color: str = "blue") -> bytes:
    image = Image.new("RGB", (width, height), color="blue")
    buffer = io.BytesIO()
    image.save(buffer, format)
    return buffer.getvalue()
