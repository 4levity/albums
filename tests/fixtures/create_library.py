import io
import os
import shutil
from pathlib import Path
from typing import Collection

from PIL import Image

from albums.database.models import AlbumEntity, TrackEntity, TrackPictureEntity
from albums.picture.format import MIME_PILLOW_FORMAT
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import Picture

from .empty_files import (
    EMPTY_AIFF_FILE_BYTES,
    EMPTY_FLAC_FILE_BYTES,
    EMPTY_M4A_FILE_BYTES,
    EMPTY_MP3_FILE_BYTES,
    EMPTY_OGG_VORBIS_FILE_BYTES,
    EMPTY_WMA_FILE_BYTES,
)

test_data_path = Path(__file__).resolve().parent / "libraries"


def create_track_file(path: Path, spec: TrackEntity):
    filename: Path = path / spec.filename
    with open(filename, "wb") as file:
        if filename.suffix == ".flac":
            file.write(EMPTY_FLAC_FILE_BYTES)
        elif filename.suffix == ".m4a":
            file.write(EMPTY_M4A_FILE_BYTES)
        elif filename.suffix == ".mp3":
            file.write(EMPTY_MP3_FILE_BYTES)
        elif filename.suffix == ".wma":
            file.write(EMPTY_WMA_FILE_BYTES)
        elif filename.suffix == ".ogg":
            file.write(EMPTY_OGG_VORBIS_FILE_BYTES)
        elif filename.suffix == ".aiff":
            file.write(EMPTY_AIFF_FILE_BYTES)
    tagger = AlbumTagger(path, padding=lambda _: 0)
    with tagger.open(spec.filename) as tags:
        for pic in spec.pictures:
            image_data = make_image_data(pic.picture_info.width, pic.picture_info.height, MIME_PILLOW_FORMAT[pic.picture_info.mime_type])
            picture = Picture(pic.picture_info, pic.picture_type, pic.description) if isinstance(pic, TrackPictureEntity) else pic
            tags.add_picture(picture, image_data)
        for tag_name, values in spec.tag_dict().items():
            tags.set_tag(tag_name, list(values))


def create_picture_file(path: Path, width: int = 400, height: int = 400, color: str = "blue"):
    image = Image.new("RGB", (width, height), color="blue")
    image.save(path)


def create_album_in_library(library_path: Path, album: AlbumEntity):
    path = library_path / album.path
    os.makedirs(path)
    for track in album.tracks:
        create_track_file(path, track)
    for file in album.picture_files:
        create_picture_file(path / file.filename, file.picture_info.width, file.picture_info.height)


def create_library(library_name: str, albums: Collection[AlbumEntity]):
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
