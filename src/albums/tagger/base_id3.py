import logging
import textwrap
from typing import Callable, Generator, List, Tuple, override

from mutagen._tags import PaddingInfo
from mutagen.aiff import AIFF
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC, TALB, TCON, TIT2, TPE1, TPE2, TPOS, TRCK
from mutagen.id3._specs import Encoding
from mutagen.mp3 import MP3

from ..config import ID3v1Policy
from ..picture.scan import PictureScanner
from .base_mutagen import AbstractMutagenTagger
from .types import BasicTag, Picture, PictureType

logger = logging.getLogger(__name__)

BASIC_ID3_TEXT_FRAMES: Tuple[Tuple[BasicTag, str], ...] = (
    (BasicTag.ALBUM, "TALB"),
    (BasicTag.ALBUMARTIST, "TPE2"),
    (BasicTag.ARTIST, "TPE1"),
    (BasicTag.TITLE, "TIT2"),
    # TCON too but we use .genres instead of .text
    # TRCK and TPOS too but they are not 1:1
)
# TODO also pull other common values, like
# "composer": "tcom",
# "encoder": "tenc",
# "date": "tdrc",  # recordingdate?


class AbstractId3Tagger[_FT: MP3 | AIFF](AbstractMutagenTagger[_FT]):
    _picture_scanner: PictureScanner
    _id3v1: ID3v1Policy

    def _get_file(self) -> _FT: ...
    def _ensure_id3(self) -> ID3: ...
    def _save(self) -> None: ...

    def __init__(self, picture_scanner: PictureScanner, padding: Callable[[PaddingInfo], int], id3v1: ID3v1Policy):
        super().__init__(padding)
        self._picture_scanner = picture_scanner
        self._id3v1 = id3v1

    def get_pictures(self) -> Generator[Tuple[Picture, bytes], None, None]:
        tags: ID3 = self._file.tags  # type: ignore
        picture_frames: list[APIC] = tags.getall("APIC") if tags else []  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        for frame in picture_frames:  # pyright: ignore[reportUnknownVariableType]
            image_data: bytes = bytes(frame.data)  # type: ignore
            picture_type = PictureType(frame.type)  # type: ignore
            expect_mime_type = str(frame.mime) if frame.mime and isinstance(frame.mime, str) else "Unknown"  # type: ignore
            description = str(frame.desc)  # type: ignore

            picture_info = self._picture_scanner.scan(image_data, expect_mime_type)
            picture = Picture(picture_info, picture_type, description)
            yield (picture, image_data)

    @override
    def _add_picture(self, new_picture: Picture, image_data: bytes) -> None:
        id3 = self._ensure_id3()
        description = new_picture.description
        apic = APIC(mime=new_picture.picture_info.mime_type, type=new_picture.type, data=image_data, desc=description)

        # with future mutagen 1.48 or later, docs indicate we will be able to ensure distinct hash key like this:
        # while apic.HashKey in tags:
        #     apic.salt += "x"
        while apic.HashKey in id3:  # TODO don't alter description
            description += " "
            apic = APIC(mime=new_picture.picture_info.mime_type, type=new_picture.type, data=image_data, desc=description)
        id3.add(apic)  # pyright: ignore[reportUnknownMemberType]

    @override
    def _remove_picture(self, remove_picture: Picture) -> None:
        if not self._get_file().tags:  # pyright: ignore[reportUnknownMemberType]
            logger.warning(f"could not remove {remove_picture.type.name} picture from {self._get_file().filename}: no ID3 tag")
            return
        id3 = self._ensure_id3()  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        pictures = list((pic, data) for pic, data in self.get_pictures() if pic != remove_picture)
        id3.delall("APIC")  # pyright: ignore[reportUnknownMemberType]
        for pic, data in pictures:
            self._add_picture(pic, data)

    @override
    def _scan_tags(self) -> Tuple[Tuple[BasicTag, Tuple[str, ...]], ...]:
        basic_tags: list[Tuple[BasicTag, Tuple[str, ...]]] = []
        if self._get_file().tags:  # pyright: ignore[reportUnknownMemberType]
            id3 = self._ensure_id3()
            basic_tags.extend((tag, tuple(_must_get_text(id3, frame))) for tag, frame in BASIC_ID3_TEXT_FRAMES if frame in id3)

            if "TCON" in id3:
                basic_tags.append((BasicTag.GENRE, tuple(id3["TCON"].genres)))  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]

            (track_number, track_total) = self._get_trck()
            if track_number is not None:
                basic_tags.append((BasicTag.TRACKNUMBER, (track_number,)))
            if track_total is not None:
                basic_tags.append((BasicTag.TRACKTOTAL, (track_total,)))

            (disc_number, disc_total) = self._get_tpos()
            if disc_number is not None:
                basic_tags.append((BasicTag.DISCNUMBER, (disc_number,)))
            if disc_total is not None:
                basic_tags.append((BasicTag.DISCTOTAL, (disc_total,)))

        return tuple(basic_tags)

    @override
    def _set_tag(self, tag: BasicTag, value: str | List[str] | None):
        tags = self._ensure_id3()
        if value is None:
            match tag:
                case BasicTag.ALBUM:
                    del tags["TALB"]
                case BasicTag.ALBUMARTIST:
                    del tags["TPE2"]
                case BasicTag.ARTIST:
                    del tags["TPE1"]
                case BasicTag.GENRE:
                    del tags["TCON"]
                case BasicTag.DISCNUMBER:
                    (_, disc_total) = self._get_tpos()
                    self._set_tpos(None, disc_total)
                case BasicTag.DISCTOTAL:
                    (disc_number, _) = self._get_tpos()
                    self._set_tpos(disc_number, None)
                case BasicTag.TITLE:
                    del tags["TIT2"]
                case BasicTag.TRACKNUMBER:
                    (_, track_total) = self._get_trck()
                    self._set_trck(None, track_total)
                case BasicTag.TRACKTOTAL:
                    (track_number, _) = self._get_trck()
                    self._set_trck(track_number, None)
        else:
            value_list = value if isinstance(value, List) else [value]
            match tag:
                case BasicTag.ALBUM:
                    tags["TALB"] = TALB(encoding=Encoding.UTF8, text=value_list)
                case BasicTag.ALBUMARTIST:
                    tags["TPE2"] = TPE2(encoding=Encoding.UTF8, text=value_list)
                case BasicTag.ARTIST:
                    tags["TPE1"] = TPE1(encoding=Encoding.UTF8, text=value_list)
                case BasicTag.DISCNUMBER:
                    (_, disc_total) = self._get_tpos()
                    self._set_tpos(value_list[0] if value_list[0] else None, disc_total)
                case BasicTag.DISCTOTAL:
                    (disc_number, _) = self._get_tpos()
                    self._set_tpos(disc_number, value_list[0] if value_list[0] else None)
                case BasicTag.GENRE:
                    tags["TCON"] = TCON(encoding=Encoding.UTF8, text=value_list)
                case BasicTag.TITLE:
                    tags["TIT2"] = TIT2(encoding=Encoding.UTF8, text=value_list)
                case BasicTag.TRACKNUMBER:
                    (_, track_total) = self._get_trck()
                    self._set_trck(value_list[0] if value_list[0] else None, track_total)
                case BasicTag.TRACKTOTAL:
                    (track_number, _) = self._get_trck()
                    self._set_trck(track_number, value_list[0] if value_list[0] else None)

    def _get_tpos(self) -> Tuple[str | None, str | None]:
        values = _get_text(self._get_file().tags, "TPOS")  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
        value = values[0] if values else None
        if value is None:
            return (None, None)
        # else
        if str.count(value, "/") == 1:
            (disc_number, disc_total) = value.split("/")
            return (disc_number, disc_total)
        # else
        return (value, None)

    def _get_trck(self) -> Tuple[str | None, str | None]:
        values = _get_text(self._get_file().tags, "TRCK")  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
        value = values[0] if values else None
        if value is None:
            return (None, None)
        # else
        if str.count(value, "/") == 1:
            (track_number, track_total) = value.split("/")
            return (track_number, track_total)
        # else
        return (value, None)

    def _set_tpos(self, disc_number: str | None, disc_total: str | None):
        if disc_number is None and disc_total is None:
            value = None
        elif disc_total is None:
            value = disc_number
        elif disc_number is None:
            value = f"/{disc_total}"
        else:
            value = f"{disc_number}/{disc_total}"

        id3 = self._ensure_id3()
        if value is None and "TPOS" in id3:
            del id3["TPOS"]
        elif value is not None and "TPOS" not in id3:
            id3.add(TPOS(encoding=Encoding.UTF8, text=[value]))  # pyright: ignore[reportUnknownMemberType]
        elif value is not None and id3["TPOS"].text != [value]:  # pyright: ignore[reportUnknownMemberType]
            id3["TPOS"] = TPOS(encoding=Encoding.UTF8, text=[value])

    def _set_trck(self, track_number: str | None, track_total: str | None):
        if track_number is None and track_total is None:
            value = None
        elif track_total is None:
            value = track_number
        elif track_number is None:
            value = f"/{track_total}"
        else:
            value = f"{track_number}/{track_total}"

        id3 = self._ensure_id3()
        if value is None and "TRCK" in id3:
            del id3["TRCK"]
        elif value is not None and "TRCK" not in id3:
            id3.add(TRCK(encoding=Encoding.UTF8, text=[value]))  # pyright: ignore[reportUnknownMemberType]
        elif value is not None and id3["TRCK"].text != [value]:  # pyright: ignore[reportUnknownMemberType]
            id3["TRCK"] = TRCK(encoding=Encoding.UTF8, text=[value])


def _get_text(id3: ID3 | None, frame_name: str):
    if id3 is None:
        return None
    if frame_name not in id3:
        return None
    return _must_get_text(id3, frame_name)


def _must_get_text(id3: ID3, frame_name: str):
    frame = id3[frame_name]  # pyright: ignore[reportUnknownVariableType]
    if hasattr(frame, "text") and isinstance(frame.text, list) and len(frame.text):  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
        return [str(text) for text in frame.text]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType, reportUnknownMemberType]
    # fallback if this does not look like a text frame
    return [textwrap.shorten(str(frame), width=4096)]  # pyright: ignore[reportUnknownArgumentType]
