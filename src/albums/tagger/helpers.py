from typing import Sequence, Tuple

from mutagen._vorbis import VCommentDict
from mutagen.flac import Picture as FlacPicture

from ..picture.scan import PictureScanner
from .types import BasicTag, Picture, PictureType


def vorbis_comment_tags(file_tags: VCommentDict):
    tags: list[tuple[BasicTag, tuple[str, ...]]] = []
    for tag in BasicTag:
        if tag.value in file_tags:
            values: Tuple[str, ...] = tuple(str(value) for value in file_tags[tag.value])  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
            tags.append((tag, values))
    return tuple(tags)


def vorbis_comment_set_tag(file_tags: VCommentDict, tag: BasicTag, value: str | Sequence[str] | None):
    if value is None:
        if tag.value in file_tags:
            del file_tags[tag.value]
    else:
        file_tags[tag.value] = [value] if isinstance(value, str) else value


def scan_flac_picture(flac_picture: FlacPicture, picture_scanner: PictureScanner) -> Tuple[Picture, bytes]:
    image_data = bytes(flac_picture.data)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
    expect_mime_type = flac_picture.mime  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    picture_info = picture_scanner.scan(image_data, expect_mime_type, flac_picture.width, flac_picture.height)  # pyright: ignore[reportUnknownArgumentType]
    description = str(flac_picture.desc) if flac_picture.desc else ""  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
    pic = Picture(picture_info, PictureType(flac_picture.type), description)
    return (pic, image_data)


def album_picture_to_flac(picture: Picture, image_data: bytes) -> FlacPicture:
    flac_picture = FlacPicture()
    flac_picture.type = picture.type
    flac_picture.mime = picture.picture_info.mime_type
    flac_picture.width = picture.picture_info.width
    flac_picture.height = picture.picture_info.height
    flac_picture.data = image_data
    flac_picture.depth = picture.picture_info.depth_bpp
    return flac_picture
