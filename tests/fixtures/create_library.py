import io
import os
import shutil
from pathlib import Path

from PIL import Image

from albums.library.metadata import mime_to_pillow_format
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import AlbumPicture, PictureInfo
from albums.types import Album, Track

from .empty_files import EMPTY_FLAC_FILE_BYTES, EMPTY_MP3_FILE_BYTES, EMPTY_OGG_VORBIS_FILE_BYTES, EMPTY_WMA_FILE_BYTES

test_data_path = Path(__file__).resolve().parent / "libraries"


def create_track_file(path: Path, spec: Track):
    filename: Path = path / spec.filename
    with open(filename, "wb") as file:
        if filename.suffix == ".flac":
            file.write(EMPTY_FLAC_FILE_BYTES)
        elif filename.suffix == ".mp3":
            file.write(EMPTY_MP3_FILE_BYTES)
        elif filename.suffix == ".wma":
            file.write(EMPTY_WMA_FILE_BYTES)
        elif filename.suffix == ".ogg":
            file.write(EMPTY_OGG_VORBIS_FILE_BYTES)
    tagger = AlbumTagger(path, padding=lambda _: 0)
    with tagger.open(spec.filename) as tags:
        for pic in spec.pictures:
            image_data = make_image_data(pic.width, pic.height, mime_to_pillow_format(pic.format, "PNG"))
            tags.add_picture(
                AlbumPicture(PictureInfo(pic.format, pic.width, pic.height, 24, pic.file_size, pic.file_hash), pic.picture_type, pic.description, ()),
                image_data,
            )
        for tag_name, values in spec.tags.items():
            tags.set_tag(BasicTag(tag_name), list(values))


def create_picture_file(path: Path, width: int = 400, height: int = 400, color: str = "blue"):
    image = Image.new("RGB", (width, height), color="blue")
    image.save(path)


def create_album_in_library(library_path: Path, album: Album):
    path = library_path / album.path
    os.makedirs(path)
    for track in album.tracks:
        create_track_file(path, track)
    for filename, pic in album.picture_files.items():
        create_picture_file(path / filename, pic.width, pic.height)


def create_library(library_name: str, albums: list[Album]):
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
