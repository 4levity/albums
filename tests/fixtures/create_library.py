import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
import os
from pathlib import Path
import shutil

from albums.types import Album, Track
from .empty_files import EMPTY_FLAC_FILE_BYTES, EMPTY_MP3_FILE_BYTES, EMPTY_WMA_FILE_BYTES


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
    mut = None
    if filename.suffix == ".flac":
        mut = FLAC(filename)
    elif filename.suffix == ".mp3":
        mut = MP3(filename, ID3=EasyID3)
    elif filename.suffix == ".wma":
        mut = mutagen.File(filename)

    if mut is not None:
        for name, value in spec.tags.items() if spec.tags else []:
            mut[name] = value
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
