import base64
import os
import shutil
from pathlib import Path
from typing import Iterable

import mutagen
from mutagen._vorbis import VCommentDict
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture
from mutagen.id3 import APIC, ID3
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis

from albums.library.metadata import MutagenFileTypeLike, TagType, set_basic_tags_file
from albums.types import Album, Picture, Track

from .empty_files import EMPTY_FLAC_FILE_BYTES, EMPTY_MP3_FILE_BYTES, EMPTY_OGG_VORBIS_FILE_BYTES, EMPTY_WMA_FILE_BYTES, IMAGE_PNG_400X400

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
    mut: MutagenFileTypeLike | None = None
    tag_type = TagType.OTHER
    if filename.suffix == ".flac":
        mut = FLAC(filename)  # pyright: ignore[reportAssignmentType]
        if mut.tags is None:
            mut.add_tags()
        _add_flac_pictures(mut, spec.pictures)  # pyright: ignore[reportArgumentType]
        tag_type = TagType.VORBIS_COMMENTS
    elif filename.suffix == ".mp3":
        mut = MP3(filename)  # pyright: ignore[reportAssignmentType]
        _add_id3_pictures(mut, spec.pictures)  # pyright: ignore[reportArgumentType]
        tag_type = TagType.ID3_FRAMES
    elif filename.suffix == ".ogg":
        mut = OggVorbis(filename)  # pyright: ignore[reportAssignmentType]
        _add_vorbis_comment_pictures(mut.tags, spec.pictures)
        tag_type = TagType.VORBIS_COMMENTS
    elif filename.suffix == ".wma":
        mut = mutagen.File(filename)

    if mut is not None:
        set_basic_tags_file(mut, list(spec.tags.items()), tag_type)

        # minimum padding ensures small changes to tags will change file size for test
        mut.save(padding=lambda info: 0)


def _add_flac_pictures(flac: FLAC, pictures: Iterable[Picture]):
    for picture in pictures:
        flac.add_picture(_make_flac_picture(picture))


def _add_id3_pictures(mp3: MP3, pictures: Iterable[Picture]):
    if mp3.tags is None:
        mp3.add_tags()
    tags: ID3 = mp3.tags  # pyright: ignore[reportAssignmentType]
    for picture in pictures:
        # TODO generate image of the specified size
        apic = APIC(mime="image/png", type=picture.picture_type, data=bytes(IMAGE_PNG_400X400))
        while apic.HashKey in tags:
            apic.salt += "x"
        tags.add(apic)


def _add_vorbis_comment_pictures(tags: VCommentDict, pictures: Iterable[Picture]):
    comment_values: list[str] = []
    for picture in pictures:
        flac_picture = _make_flac_picture(picture)
        comment_values.append(base64.b64encode(flac_picture.write()).decode("ascii"))
    if comment_values:
        tags["metadata_block_picture"] = comment_values


def _make_flac_picture(picture: Picture) -> FlacPicture:
    pic = FlacPicture()
    pic.data = IMAGE_PNG_400X400  # TODO generate image of the specified size
    pic.type = picture.picture_type  # other spec properites ignored
    pic.mime = "image/png"
    pic.width = 400
    pic.height = 400
    pic.depth = 8
    return pic


def create_picture_file(path: Path, filename: str):
    # TODO create size/type specified
    target = path / filename
    if str.lower(target.suffix) != ".png":
        raise NotImplementedError
    with open(target, "wb") as file:
        file.write(IMAGE_PNG_400X400)


def create_album_in_library(library_path: Path, album: Album):
    path = library_path / album.path
    os.makedirs(path)
    for track in album.tracks:
        create_track_file(path, track)
    for filename in album.picture_files:
        create_picture_file(path, filename)


def create_library(library_name: str, albums: list[Album]):
    library_path = test_data_path / library_name
    shutil.rmtree(library_path, ignore_errors=True)
    os.makedirs(library_path)
    for album in albums:
        create_album_in_library(library_path, album)
    return library_path
