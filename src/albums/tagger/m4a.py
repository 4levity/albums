import logging
from copy import copy
from pathlib import Path
from typing import Callable, Generator, List, Tuple, override

from mutagen._tags import PaddingInfo
from mutagen.mp4 import MP4, MP4Cover, MP4Tags

from ..picture.scan import PictureScanner
from .base_mutagen import AbstractMutagenTagger
from .types import BasicTag, Picture, PictureType

logger = logging.getLogger(__name__)


BASIC_M4A_TEXT_FRAMES: Tuple[Tuple[BasicTag, str], ...] = (
    (BasicTag.ALBUM, "©alb"),
    (BasicTag.ALBUMARTIST, "aART"),
    (BasicTag.ARTIST, "©ART"),
    (BasicTag.TITLE, "©nam"),
    # trkn and disk too but they are not text or 1:1
)


class M4aTagger(AbstractMutagenTagger):
    _file: MP4
    _picture_scanner: PictureScanner

    def __init__(self, path: Path, picture_scanner: PictureScanner, padding: Callable[[PaddingInfo], int]):
        super().__init__(padding)
        self._file = MP4(path)
        self._padding = padding
        self._picture_scanner = picture_scanner

    @override
    def get_pictures(self) -> Generator[Tuple[Picture, bytes], None, None]:
        if not self._file.tags:
            return
        mp4_covers: list[MP4Cover] = self._file.tags["covr"] if "covr" in self._file.tags else []  # pyright: ignore[reportUnknownVariableType]
        for cover in mp4_covers:  # pyright: ignore[reportUnknownVariableType]
            match cover.imageformat:  # pyright: ignore[reportUnknownMemberType]
                case MP4Cover.FORMAT_JPEG:
                    expect_mime_type = "image/jpeg"
                case MP4Cover.FORMAT_PNG:
                    expect_mime_type = "image/png"
                case _:  # pyright: ignore[reportUnknownVariableType]
                    expect_mime_type = "invalid"  # causes loader to report MIME type mismatch

            image_data = bytes(cover)  # pyright: ignore[reportUnknownArgumentType]
            picture_info = self._picture_scanner.scan(image_data, expect_mime_type)
            picture = Picture(picture_info, PictureType.COVER_FRONT, "")
            yield (picture, image_data)

    @override
    def _add_picture(self, new_picture: Picture, image_data: bytes) -> None:
        if new_picture.file_info.mime_type == "image/jpeg":
            imageformat = MP4Cover.FORMAT_JPEG
        elif new_picture.file_info.mime_type == "image/png":
            imageformat = MP4Cover.FORMAT_PNG
        else:
            raise ValueError(f"unsupported MIME type {new_picture.file_info.mime_type} for saving in covr tag")
        if new_picture.type != PictureType.COVER_FRONT:
            logger.warning(f'embedding picture {new_picture.type.name} as "cover", picture type not supported in {self._file.filename}')

        tags = self._ensure_tags()
        covers: list[MP4Cover] = tags["covr"] if "covr" in tags else []  # pyright: ignore[reportUnknownVariableType]
        covers.append(MP4Cover(image_data, imageformat))  # pyright: ignore[reportUnknownMemberType]
        tags["covr"] = covers

    @override
    def _get_file(self):
        return self._file

    @override
    def _remove_picture(self, remove_picture: Picture) -> None:
        if not self._file.tags:
            return
        pictures: list[tuple[Picture, bytes]] = [(copy(pic), image_data) for pic, image_data in self.get_pictures() if pic != remove_picture]
        del self._file.tags["covr"]
        for pic, data in pictures:
            self._add_picture(pic, data)

    @override
    def _scan_tags(self) -> Tuple[Tuple[BasicTag, Tuple[str, ...]], ...]:
        basic_tags: list[Tuple[BasicTag, Tuple[str, ...]]] = []
        if self._file.tags:  # pyright: ignore[reportUnknownMemberType]
            tags = self._ensure_tags()
            basic_tags.extend((tag, tuple(tags[atom])) for tag, atom in BASIC_M4A_TEXT_FRAMES if atom in tags)  # pyright: ignore[reportUnknownArgumentType]

            (track_number, track_total) = self._get_trkn()
            if track_number:
                basic_tags.append((BasicTag.TRACKNUMBER, (str(track_number),)))
            if track_total:
                basic_tags.append((BasicTag.TRACKTOTAL, (str(track_total),)))

            (disc_number, disc_total) = self._get_disk()
            if disc_number is not None:
                basic_tags.append((BasicTag.DISCNUMBER, (str(disc_number),)))
            if disc_total is not None:
                basic_tags.append((BasicTag.DISCTOTAL, (str(disc_total),)))

        return tuple(basic_tags)

    @override
    def _set_tag(self, tag: BasicTag, value: str | List[str] | None):
        tags = self._ensure_tags()

        if value is None:
            match tag:
                case BasicTag.ALBUM:
                    del tags["©alb"]
                case BasicTag.ALBUMARTIST:
                    del tags["aART"]
                case BasicTag.ARTIST:
                    del tags["©ART"]
                case BasicTag.DISCNUMBER:
                    (_, disc_total) = self._get_disk()
                    self._set_disk(None, disc_total)
                case BasicTag.DISCTOTAL:
                    (disc_number, _) = self._get_disk()
                    self._set_disk(disc_number, None)
                case BasicTag.TITLE:
                    del tags["©nam"]
                case BasicTag.TRACKNUMBER:
                    (_, track_total) = self._get_trkn()
                    self._set_trkn(None, track_total)
                case BasicTag.TRACKTOTAL:
                    (track_number, _) = self._get_trkn()
                    self._set_trkn(track_number, None)
        else:
            value_list = value if isinstance(value, List) else [value]
            match tag:
                case BasicTag.ALBUM:
                    tags["©alb"] = value_list
                case BasicTag.ALBUMARTIST:
                    tags["aART"] = value_list
                case BasicTag.ARTIST:
                    tags["©ART"] = value_list
                case BasicTag.DISCNUMBER:
                    (_, disc_total) = self._get_disk()
                    self._set_disk(int(value_list[0]) if value_list[0] else None, disc_total)
                case BasicTag.DISCTOTAL:
                    (disc_number, _) = self._get_disk()
                    self._set_disk(disc_number, int(value_list[0]) if value_list[0] else None)
                case BasicTag.TITLE:
                    tags["©nam"] = value_list
                case BasicTag.TRACKNUMBER:
                    (_, track_total) = self._get_trkn()
                    self._set_trkn(int(value_list[0]) if value_list[0] else None, track_total)
                case BasicTag.TRACKTOTAL:
                    (track_number, _) = self._get_trkn()
                    self._set_trkn(track_number, int(value_list[0]) if value_list[0] else None)

    def _ensure_tags(self) -> MP4Tags:
        if not self._file.tags:
            self._file.add_tags()
        return self._file.tags  # pyright: ignore[reportReturnType]

    def _get_disk(self) -> Tuple[int | None, int | None]:
        if not self._file.tags or "disk" not in self._file.tags:
            return (None, None)
        values = self._file.tags["disk"]  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(values, list) or len(values) < 1 or not isinstance(values[0], tuple):  # pyright: ignore[reportUnknownArgumentType]
            return (None, None)
        disk: Tuple[int, int] = values[0]  # pyright: ignore[reportUnknownVariableType]
        (disc_number, disc_total) = disk
        return (disc_number if disc_number else None, disc_total if disc_total else None)

    def _get_trkn(self) -> Tuple[int | None, int | None]:
        if not self._file.tags or "trkn" not in self._file.tags:
            return (None, None)
        values = self._file.tags["trkn"]  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(values, list) or len(values) < 1 or not isinstance(values[0], tuple):  # pyright: ignore[reportUnknownArgumentType]
            return (None, None)
        disk: Tuple[int, int] = values[0]  # pyright: ignore[reportUnknownVariableType]
        (track_number, track_total) = disk
        return (track_number if track_number else None, track_total if track_total else None)

    def _set_disk(self, disc_number: int | None, disc_total: int | None):
        tags = self._ensure_tags()
        tags["disk"] = [(disc_number if disc_number else 0, disc_total if disc_total else 0)]

    def _set_trkn(self, track_number: int | None, track_total: int | None):
        tags = self._ensure_tags()
        tags["trkn"] = [(track_number if track_number else 0, track_total if track_total else 0)]
