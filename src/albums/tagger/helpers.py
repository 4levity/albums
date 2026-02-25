import io
from typing import List, Tuple

from mutagen._vorbis import VCommentDict
from mutagen.flac import Picture as FlacPicture
from PIL import Image

from .picture import PictureScanner
from .types import AlbumPicture, BasicTag, PictureType


def vorbis_comment_tags(file_tags: VCommentDict):
    tags: list[tuple[BasicTag, tuple[str, ...]]] = []
    for tag in BasicTag:
        if tag.value in file_tags:
            values: Tuple[str, ...] = tuple(str(value) for value in file_tags[tag.value])  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
            tags.append((tag, values))
    return tuple(tags)


def vorbis_comment_set_tag(file_tags: VCommentDict, tag: BasicTag, value: str | List[str] | None):
    if value is None:
        if tag.value in file_tags:
            del file_tags[tag.value]
    else:
        file_tags[tag.value] = [value] if isinstance(value, str) else value


def scan_flac_picture(flac_picture: FlacPicture, picture_scanner: PictureScanner):
    image_data: bytes = flac_picture.data  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    expect_mime_type = flac_picture.mime  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    result = picture_scanner.scan(image_data, expect_mime_type, flac_picture.width, flac_picture.height)  # pyright: ignore[reportUnknownArgumentType]
    description = str(flac_picture.desc) if flac_picture.desc else ""  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
    return AlbumPicture(result.picture_info, PictureType(flac_picture.type), description, result.load_issue)


def album_picture_to_flac(picture: AlbumPicture, image_data: bytes, image_mode: str | None = None) -> FlacPicture:
    flac_picture = FlacPicture()
    flac_picture.type = picture.picture_type
    flac_picture.mime = picture.file_info.mime_type
    flac_picture.width = picture.file_info.width
    flac_picture.height = picture.file_info.height
    flac_picture.data = image_data
    if image_mode is None:
        image = Image.open(io.BytesIO(image_data))
        image_mode = image.mode
        image.close()
    flac_picture.depth = picture.file_info.depth_bpp
    return flac_picture
