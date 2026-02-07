import os
import shutil
from pathlib import Path

import mutagen
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture
from mutagen.mp3 import MP3

from albums.library.metadata import MutagenFileTypeLike, TagType, set_basic_tags_file
from albums.types import Album, Track

from .empty_files import EMPTY_FLAC_FILE_BYTES, EMPTY_MP3_FILE_BYTES, EMPTY_WMA_FILE_BYTES, IMAGE_PNG_400X400

test_data_path = Path(__file__).resolve().parent / "libraries"


def create_file(path: Path, spec: Track):
    filename: Path = path / spec.filename
    with open(filename, "wb") as file:
        if filename.suffix == ".flac":
            file.write(EMPTY_FLAC_FILE_BYTES)
        elif filename.suffix == ".mp3":
            file.write(EMPTY_MP3_FILE_BYTES)
        elif filename.suffix == ".wma":
            file.write(EMPTY_WMA_FILE_BYTES)
    mut: MutagenFileTypeLike | None = None
    tag_type = TagType.OTHER
    if filename.suffix == ".flac":
        mut = FLAC(filename)  # pyright: ignore[reportAssignmentType]
        tag_type = TagType.VORBIS_COMMENTS
        for picture in spec.pictures:
            pic = FlacPicture()
            pic.data = IMAGE_PNG_400X400  # TODO generate image of the specified size
            pic.type = picture.picture_type  # other spec properites ignored
            pic.mime = "image/png"
            pic.width = 400
            pic.height = 400
            pic.depth = 8
            mut.add_picture(pic)
    elif filename.suffix == ".mp3":
        mut = MP3(filename)  # pyright: ignore[reportAssignmentType]
        tag_type = TagType.ID3_FRAMES
    elif filename.suffix == ".wma":
        mut = mutagen.File(filename)

    if mut is not None:
        set_basic_tags_file(mut, list(spec.tags.items()), tag_type)

        # minimum padding ensures small changes to tags will change file size for test
        mut.save(padding=lambda info: 0)


def create_album_in_library(library_path: Path, album: Album):
    path = library_path / album.path
    os.makedirs(path)
    for track in album.tracks:
        create_file(path, track)


def create_library(library_name: str, albums: list[Album]):
    library_path = test_data_path / library_name
    shutil.rmtree(library_path, ignore_errors=True)
    os.makedirs(library_path)
    for album in albums:
        create_album_in_library(library_path, album)
    return library_path
