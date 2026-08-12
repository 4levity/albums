import logging
from typing import Callable, Final, Generator, List, Tuple, override

from mutagen._tags import PaddingInfo
from mutagen.aiff import AIFF
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC, TALB, TCMP, TCON, TIT2, TPE1, TPE2, TPOS, TPUB, TRCK, TSO2, TSOA, TSOP, TXXX, UFID
from mutagen.id3._specs import Encoding
from mutagen.mp3 import MP3

from ..config import ID3v1Policy
from ..picture.scan import PictureScanner
from .base_mutagen import AbstractMutagenTagger
from .id3_helpers import format_numbered_value, get_text, must_get_text, parse_numbered_value, set_numbered_frame
from .id3_mappings import BASIC_ID3_TEXT_FRAMES, FIELD_TO_ID3_TEXT_FRAME, UFID_MUSICBRAINZ_OWNER
from .types import BasicField, Picture, PictureType

logger: Final = logging.getLogger(__name__)


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
        frames = self._ensure_id3()
        picture_frames: list[APIC] = frames.getall("APIC") if frames else []  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
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
        frames = self._ensure_id3()
        description = new_picture.description
        apic = APIC(mime=new_picture.picture_info.mime_type, type=new_picture.type, data=image_data, desc=description)
        # with future mutagen 1.48 or later, docs indicate we will be able to ensure distinct hash key like this:
        # while apic.HashKey in tags:
        #     apic.salt += "x"
        while apic.HashKey in frames:  # TODO don't alter description
            description += " "
            apic = APIC(mime=new_picture.picture_info.mime_type, type=new_picture.type, data=image_data, desc=description)
        frames.add(apic)  # pyright: ignore[reportUnknownMemberType]

    @override
    def _remove_picture(self, remove_picture: Picture) -> None:
        if not self._get_file().tags:  # pyright: ignore[reportUnknownMemberType]
            logger.warning(f"could not remove {remove_picture.type.name} picture from {self._get_file().filename}: no ID3 tag")
            return
        frames = self._ensure_id3()  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        pictures = list((pic, data) for pic, data in self.get_pictures() if pic != remove_picture)
        frames.delall("APIC")  # pyright: ignore[reportUnknownMemberType]
        for pic, data in pictures:
            self._add_picture(pic, data)

    @override
    def get_fields(self) -> Tuple[Tuple[BasicField, Tuple[str, ...]], ...]:
        basic_fields: list[Tuple[BasicField, Tuple[str, ...]]] = []
        if self._get_file().tags:  # pyright: ignore[reportUnknownMemberType]
            frames = self._ensure_id3()
            basic_fields.extend((tag, tuple(must_get_text(frames, frame))) for tag, frame in BASIC_ID3_TEXT_FRAMES if frame in frames)

            if "TCON" in frames:
                basic_fields.append((BasicField.GENRE, tuple(frames["TCON"].genres)))  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]

            ufid_frame = f"UFID:{UFID_MUSICBRAINZ_OWNER}"
            if ufid_frame in frames:
                ufid_data = bytes(frames[ufid_frame].data)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
                basic_fields.append((BasicField.MUSICBRAINZ_TRACKID, (ufid_data.decode("ascii"),)))

            track_number, track_total = self._get_trck()
            if track_number is not None:
                basic_fields.append((BasicField.TRACKNUMBER, (track_number,)))
            if track_total is not None:
                basic_fields.append((BasicField.TRACKTOTAL, (track_total,)))

            disc_number, disc_total = self._get_tpos()
            if disc_number is not None:
                basic_fields.append((BasicField.DISCNUMBER, (disc_number,)))
            if disc_total is not None:
                basic_fields.append((BasicField.DISCTOTAL, (disc_total,)))

        return tuple(basic_fields)

    @override
    def _set_field(self, field: BasicField | str, value: str | List[str] | None):
        if not isinstance(field, BasicField):
            raise ValueError("id3 tagger only uses BasicField")
        frames = self._ensure_id3()
        if value is None:
            match field:
                case BasicField.GENRE:
                    del frames["TCON"]
                case BasicField.DISCNUMBER:
                    _, disc_total = self._get_tpos()
                    self._set_tpos(None, disc_total)
                case BasicField.DISCTOTAL:
                    disc_number, _ = self._get_tpos()
                    self._set_tpos(disc_number, None)
                case BasicField.MUSICBRAINZ_TRACKID:
                    del frames[f"UFID:{UFID_MUSICBRAINZ_OWNER}"]
                case BasicField.TRACKNUMBER:
                    _, track_total = self._get_trck()
                    self._set_trck(None, track_total)
                case BasicField.TRACKTOTAL:
                    track_number, _ = self._get_trck()
                    self._set_trck(track_number, None)
                case BasicField.UNKNOWN:
                    pass
                case _:
                    del frames[FIELD_TO_ID3_TEXT_FRAME[field]]
        else:
            value_list = value if isinstance(value, List) else [value]
            match field:
                case BasicField.ALBUM:
                    frames["TALB"] = TALB(encoding=Encoding.UTF8, text=value_list)
                case BasicField.ALBUMSORT:
                    frames["TSOA"] = TSOA(encoding=Encoding.UTF8, text=value_list)
                case BasicField.ALBUMARTIST:
                    frames["TPE2"] = TPE2(encoding=Encoding.UTF8, text=value_list)
                case BasicField.ALBUMARTISTSORT:
                    frames["TSO2"] = TSO2(encoding=Encoding.UTF8, text=value_list)
                case BasicField.ARTIST:
                    frames["TPE1"] = TPE1(encoding=Encoding.UTF8, text=value_list)
                case BasicField.ARTISTSORT:
                    frames["TSOP"] = TSOP(encoding=Encoding.UTF8, text=value_list)
                case BasicField.COMPILATION:
                    if value_list and value_list[0]:
                        frames["TCMP"] = TCMP(encoding=Encoding.UTF8, text=["1"])
                    elif "TCMP" in frames:
                        del frames["TCMP"]
                case BasicField.DISCNUMBER:
                    _, disc_total = self._get_tpos()
                    self._set_tpos(value_list[0] if value_list[0] else None, disc_total)
                case BasicField.DISCTOTAL:
                    disc_number, _ = self._get_tpos()
                    self._set_tpos(disc_number, value_list[0] if value_list[0] else None)
                case BasicField.GENRE:
                    frames["TCON"] = TCON(encoding=Encoding.UTF8, text=value_list)
                case BasicField.MUSICBRAINZ_TRACKID:
                    frames[f"UFID:{UFID_MUSICBRAINZ_OWNER}"] = UFID(owner=UFID_MUSICBRAINZ_OWNER, data=bytes(value_list[0], "utf-8"))
                case BasicField.RELEASECOUNTRY | BasicField.RELEASETYPE:
                    raise ValueError(f"cannot set {field.name} in ID3 tag on {self._get_file().filename}")
                case BasicField.ORGANIZATION:
                    frames["TPUB"] = TPUB(encoding=Encoding.UTF8, text=value_list)
                case BasicField.TITLE:
                    frames["TIT2"] = TIT2(encoding=Encoding.UTF8, text=value_list)
                case BasicField.TRACKNUMBER:
                    _, track_total = self._get_trck()
                    self._set_trck(value_list[0] if value_list[0] else None, track_total)
                case BasicField.TRACKTOTAL:
                    track_number, _ = self._get_trck()
                    self._set_trck(track_number, value_list[0] if value_list[0] else None)
                case BasicField.UNKNOWN:
                    raise ValueError("cannot set tag value UNKNOWN")
                case _:
                    frame = FIELD_TO_ID3_TEXT_FRAME[field]
                    if not frame.startswith("TXXX:"):
                        raise RuntimeError(f"unexpected frame {frame}")
                    [_, description] = frame.split(":", 1)
                    frames[frame] = TXXX(encoding=Encoding.UTF8, desc=description, text=value_list)

    def _get_tpos(self) -> Tuple[str | None, str | None]:
        values = get_text(self._ensure_id3(), "TPOS")
        return parse_numbered_value(values[0] if values else None)

    def _get_trck(self) -> Tuple[str | None, str | None]:
        values = get_text(self._ensure_id3(), "TRCK")
        return parse_numbered_value(values[0] if values else None)

    def _set_tpos(self, disc_number: str | None, disc_total: str | None):
        value = format_numbered_value(disc_number, disc_total)
        set_numbered_frame(self._ensure_id3(), value, "TPOS", TPOS)

    def _set_trck(self, track_number: str | None, track_total: str | None):
        value = format_numbered_value(track_number, track_total)
        set_numbered_frame(self._ensure_id3(), value, "TRCK", TRCK)
