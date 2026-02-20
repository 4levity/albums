import io
import os
import shutil
from pathlib import Path

import mutagen
from mutagen._vorbis import VCommentDict
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
from PIL import Image

from albums.library.metadata import (
    Iterable,
    MutagenFileTypeLike,
    TagType,
    add_id3_pictures,
    flac_picture_to_vorbis_comment_value,
    mime_to_pillow_format,
    set_basic_tags_file,
)
from albums.types import Album, Picture, Track

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
    mut: MutagenFileTypeLike | None = None
    tag_type = TagType.OTHER
    if filename.suffix == ".flac":
        mut = FLAC(filename)  # pyright: ignore[reportAssignmentType]
        add_generated_flac_pictures(mut, spec.pictures)  # pyright: ignore[reportArgumentType]
        tag_type = TagType.VORBIS_COMMENTS
    elif filename.suffix == ".mp3":
        mut = MP3(filename)  # pyright: ignore[reportAssignmentType]
        add_generated_id3_pictures(mut, spec.pictures)  # pyright: ignore[reportArgumentType]
        tag_type = TagType.ID3_FRAMES
    elif filename.suffix == ".ogg":
        mut = OggVorbis(filename)  # pyright: ignore[reportAssignmentType]
        add_generated_vorbis_comment_pictures(mut.tags, spec.pictures)
        tag_type = TagType.VORBIS_COMMENTS
    elif filename.suffix == ".wma":
        mut = mutagen.File(filename)

    if mut is not None:
        set_basic_tags_file(mut, list(spec.tags.items()), tag_type)

        # minimum padding ensures small changes to tags will change file size for test
        mut.save(padding=lambda info: 0)


def add_generated_id3_pictures(mp3: MP3, pictures: Iterable[Picture]):
    if mp3.tags is None:
        mp3.add_tags()
    add_id3_pictures(
        mp3.tags,  # pyright: ignore[reportArgumentType]
        [
            (
                pic,
                make_image_data(pic.width, pic.height, mime_to_pillow_format(pic.format, "PNG")),
            )
            for pic in pictures
        ],
    )


def add_generated_flac_pictures(flac: FLAC, pictures: Iterable[Picture]):
    if flac.tags is None:
        flac.add_tags()
    for picture in pictures:
        flac.add_picture(_make_flac_picture(picture))  # pyright: ignore[reportUnknownMemberType]


def add_generated_vorbis_comment_pictures(tags: VCommentDict, pictures: Iterable[Picture]):
    _add_flac_pictures_to_vorbis_comments(tags, (_make_flac_picture(picture) for picture in pictures))


def _add_flac_pictures_to_vorbis_comments(tags: VCommentDict, flac_pictures: Iterable[FlacPicture]):
    comment_values: list[str] = []
    for flac_picture in flac_pictures:
        comment_values.append(flac_picture_to_vorbis_comment_value(flac_picture))
    if comment_values:
        tags["metadata_block_picture"] = comment_values


def _make_flac_picture(picture: Picture) -> FlacPicture:
    pic = FlacPicture()
    pic.data = make_image_data(picture.width, picture.height, mime_to_pillow_format(picture.format, "PNG"))
    pic.type = picture.picture_type  # other spec properites ignored
    pic.mime = "image/png"
    pic.width = 400
    pic.height = 400
    pic.depth = 8
    return pic


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
