import logging
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generator, List, Tuple, override

from mutagen._tags import PaddingInfo
from mutagen.asf import ASF, ASFTags
from mutagen.asf._attrs import ASFByteArrayAttribute

from ...picture.scan import PictureScanner
from ..base_mutagen import AbstractMutagenTagger
from ..types import BasicTag, Picture, PictureType

logger = logging.getLogger(__name__)


BASIC_ASF_PROPERTIES: Tuple[Tuple[BasicTag, str], ...] = (
    (BasicTag.ALBUM, "WM/AlbumTitle"),
    (BasicTag.ALBUMARTIST, "WM/AlbumArtist"),
    (BasicTag.ARTIST, "Author"),
    (BasicTag.TITLE, "Title"),
    (BasicTag.GENRE, "WM/Genre"),
    # WM/TrackNumber and WM/PartOfSet too but they are not 1:1
)


@dataclass(frozen=True)
class WmPicture:
    picture_type: PictureType
    mime_type: str
    description: str
    image_data: bytes

    def to_bytes(self) -> bytes:
        return (
            struct.pack("<bi", self.picture_type.value, len(self.image_data))
            + self.mime_type.encode("utf-16-le")
            + b"\x00\x00"
            + self.description.encode("utf-16-le")
            + b"\x00\x00"
            + self.image_data
        )

    @classmethod
    def from_bytes(cls, raw: bytes):
        (picture_type, image_data_length) = struct.unpack_from("<bi", raw)
        ix = 5
        mime_type_b = b""
        while raw[ix : ix + 2] != b"\x00\x00":
            mime_type_b += raw[ix : ix + 2]
            ix += 2
        ix += 2
        mime_type = mime_type_b.decode("utf-16-le")
        description_b = b""
        while raw[ix : ix + 2] != b"\x00\x00":
            description_b += raw[ix : ix + 2]
            ix += 2
        ix += 2
        description = description_b.decode("utf-16-le")
        image_data = raw[ix : ix + image_data_length]
        if len(raw) != ix + len(image_data):
            logger.warning("embedded image is smaller than raw data")  # if the raw data was too small, an exception was raised above
        return WmPicture(PictureType(picture_type), mime_type, description, image_data)


class AsfTagger(AbstractMutagenTagger[ASF]):
    _file: ASF
    _picture_scanner: PictureScanner

    def __init__(self, path: Path, picture_scanner: PictureScanner, padding: Callable[[PaddingInfo], int]):
        super().__init__(padding)
        self._file = ASF(path)
        self._picture_scanner = picture_scanner

    @override
    def get_pictures(self) -> Generator[Tuple[Picture, bytes], None, None]:
        if not self._file.tags:
            return
        for wm_picture_attr in self._file.tags.get("WM/Picture", []) or []:  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
            if not isinstance(wm_picture_attr, ASFByteArrayAttribute):
                logger.warning(f"unexpected WM/Picture property is not ASFByteArrayAttribute: {type(wm_picture_attr)}")  # pyright: ignore[reportUnknownArgumentType]
                continue

            try:  # TODO find a WMA file that has embedded art, test this out, and if it works, implement writing
                wm_picture = WmPicture.from_bytes(wm_picture_attr.value)  # pyright: ignore[reportArgumentType, reportUnknownMemberType]
                picture_info = self._picture_scanner.scan(wm_picture.image_data, wm_picture.mime_type)
                yield (Picture(picture_info, wm_picture.picture_type, wm_picture.description), wm_picture.image_data)
            except Exception as ex:
                logger.warning("failed to extract image from WM/Picture property, probably a bug:")
                logger.warning(repr(ex))

    @override
    def _add_picture(self, new_picture: Picture, image_data: bytes) -> None:
        raise NotImplementedError()

    @override
    def _get_file(self):
        return self._file

    @override
    def _remove_picture(self, remove_picture: Picture) -> None:
        raise NotImplementedError()

    @override
    def _scan_tags(self) -> Tuple[Tuple[BasicTag, Tuple[str, ...]], ...]:
        basic_tags: list[Tuple[BasicTag, Tuple[str, ...]]] = []
        if self._file.tags:  # pyright: ignore[reportUnknownMemberType]
            tags = self._ensure_tags()
            basic_tags.extend((tag, tuple(self._property_to_text(p) for p in tags[prop])) for tag, prop in BASIC_ASF_PROPERTIES if prop in tags)  # pyright: ignore[reportUnknownVariableType]

            (track_number, track_total) = self._get_wm_tracknumber()
            if track_number:
                basic_tags.append((BasicTag.TRACKNUMBER, (str(track_number),)))
            if track_total:
                basic_tags.append((BasicTag.TRACKTOTAL, (str(track_total),)))

            (disc_number, disc_total) = self._get_wm_partofset()
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
                    del tags["WM/AlbumTitle"]
                case BasicTag.ALBUMARTIST:
                    del tags["WM/AlbumArtist"]
                case BasicTag.ARTIST:
                    del tags["Author"]
                case BasicTag.GENRE:
                    del tags["WM/Genre"]
                case BasicTag.DISCNUMBER:
                    (_, disc_total) = self._get_wm_partofset()
                    self._set_wm_partofset(None, disc_total)
                case BasicTag.DISCTOTAL:
                    (disc_number, _) = self._get_wm_partofset()
                    self._set_wm_partofset(disc_number, None)
                case BasicTag.TITLE:
                    del tags["Title"]
                case BasicTag.TRACKNUMBER:
                    (_, track_total) = self._get_wm_tracknumber()
                    self._set_wm_tracknumber(None, track_total)
                case BasicTag.TRACKTOTAL:
                    (track_number, _) = self._get_wm_tracknumber()
                    self._set_wm_tracknumber(track_number, None)
        else:
            value_list = value if isinstance(value, List) else [value]
            match tag:
                case BasicTag.ALBUM:
                    tags["WM/AlbumTitle"] = value_list
                case BasicTag.ALBUMARTIST:
                    tags["WM/AlbumArtist"] = value_list
                case BasicTag.ARTIST:
                    tags["Author"] = value_list
                case BasicTag.GENRE:
                    tags["WM/Genre"] = value_list
                case BasicTag.DISCNUMBER:
                    (_, disc_total) = self._get_wm_partofset()
                    self._set_wm_partofset(value_list[0] if value_list[0] else None, disc_total)
                case BasicTag.DISCTOTAL:
                    (disc_number, _) = self._get_wm_partofset()
                    self._set_wm_partofset(disc_number, value_list[0] if value_list[0] else None)
                case BasicTag.TITLE:
                    tags["Title"] = value_list
                case BasicTag.TRACKNUMBER:
                    (_, track_total) = self._get_wm_tracknumber()
                    self._set_wm_tracknumber(value_list[0] if value_list[0] else None, track_total)
                case BasicTag.TRACKTOTAL:
                    (track_number, _) = self._get_wm_tracknumber()
                    self._set_wm_tracknumber(track_number, value_list[0] if value_list[0] else None)

    def _ensure_tags(self) -> ASFTags:
        if not self._file.tags:
            self._file.add_tags()
        return self._file.tags

    def _property_to_text(self, property: Any) -> str:
        if hasattr(property, "value"):
            return str(property.value)
        return str(property)

    def _get_wm_partofset(self) -> Tuple[str | None, str | None]:
        if not self._file.tags or "WM/PartOfSet" not in self._file.tags:
            return (None, None)
        values = self._file.tags["WM/PartOfSet"]  # pyright: ignore[reportUnknownVariableType]
        # TODO handle if stored as integer if mutagen doesn't do that automatically (?) +in tracknumber
        if not isinstance(values, list) or len(values) < 1 or not values:  # pyright: ignore[reportUnnecessaryIsInstance, reportUnknownArgumentType]
            return (None, None)
        value = str(values[0])  # pyright: ignore[reportUnknownArgumentType]
        if str.count(value, "/") == 1:
            (disc_number, disc_total) = value.split("/")
            return (disc_number, disc_total)
        # else
        return (value, None)

    def _get_wm_tracknumber(self) -> Tuple[str | None, str | None]:
        if not self._file.tags or "WM/TrackNumber" not in self._file.tags:
            return (None, None)
        values = self._file.tags["WM/TrackNumber"]  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(values, list) or len(values) < 1 or not values:  # pyright: ignore[reportUnnecessaryIsInstance, reportUnknownArgumentType]
            return (None, None)
        value = str(values[0])  # pyright: ignore[reportUnknownArgumentType]
        if str.count(value, "/") == 1:
            (track_number, track_total) = value.split("/")
            return (track_number, track_total)
        # else
        return (value, None)

    def _set_wm_partofset(self, disc_number: str | None, disc_total: str | None):
        if disc_number is None and disc_total is None:
            value = None
        elif disc_total is None:
            value = disc_number
        elif disc_number is None:
            value = f"/{disc_total}"
        else:
            value = f"{disc_number}/{disc_total}"

        tags = self._ensure_tags()
        if value is None and "WM/PartOfSet" in tags:
            del tags["WM/PartOfSet"]
        elif value is not None and ("WM/PartOfSet" not in tags or tags["WM/PartOfSet"] != [value]):
            tags["WM/PartOfSet"] = [value]

    def _set_wm_tracknumber(self, track_number: str | None, track_total: str | None):
        if track_number is None and track_total is None:
            value = None
        elif track_total is None:
            value = track_number
        elif track_number is None:
            value = f"/{track_total}"
        else:
            value = f"{track_number}/{track_total}"

        tags = self._ensure_tags()
        if value is None and "WM/TrackNumber" in tags:
            del tags["WM/TrackNumber"]
        elif value is not None and ("WM/TrackNumber" not in tags or tags["WM/TrackNumber"] != [value]):
            tags["WM/TrackNumber"] = [value]
