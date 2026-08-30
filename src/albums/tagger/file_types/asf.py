import logging
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Final, Generator, List, Tuple, override

from mutagen._tags import PaddingInfo
from mutagen.asf import ASF, ASFTags
from mutagen.asf._attrs import ASFByteArrayAttribute

from ...picture.scan import PictureScanner
from ..base_mutagen import AbstractMutagenTagger
from ..types import BasicField, Picture, PictureType

logger: Final = logging.getLogger(__name__)


BASIC_ASF_PROPERTIES: Final[Tuple[Tuple[BasicField, str], ...]] = (
    (BasicField.ALBUM, "WM/AlbumTitle"),
    (BasicField.ALBUMSORT, "WM/AlbumSortOrder"),
    (BasicField.ALBUMARTIST, "WM/AlbumArtist"),
    (BasicField.ALBUMARTISTSORT, "WM/AlbumArtistSortOrder"),
    (BasicField.ARTIST, "Author"),
    (BasicField.ARTISTSORT, "WM/ArtistSortOrder"),
    (BasicField.BARCODE, "WM/Barcode"),
    (BasicField.COMPILATION, "WM/IsCompilation"),
    (BasicField.GENRE, "WM/Genre"),
    (BasicField.MUSICBRAINZ_ALBUMARTISTID, "MusicBrainz/Album Artist Id"),
    (BasicField.MUSICBRAINZ_ALBUMID, "MusicBrainz/Album Id"),
    (BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY, "MusicBrainz/Album Release Country"),
    (BasicField.MUSICBRAINZ_ALBUMRELEASETYPE, "MusicBrainz/Album Release Type"),
    (BasicField.MUSICBRAINZ_ARRANGERID, "MusicBrainz/Arranger Id"),
    (BasicField.MUSICBRAINZ_ARTISTID, "MusicBrainz/Artist Id"),
    (BasicField.MUSICBRAINZ_COMPOSERID, "MusicBrainz/Composer Id"),
    (BasicField.MUSICBRAINZ_CONDUCTORID, "MusicBrainz/Conductor Id"),
    (BasicField.MUSICBRAINZ_DIRECTORID, "MusicBrainz/Director Id"),
    (BasicField.MUSICBRAINZ_DISCID, "MusicBrainz/Disc Id"),
    (BasicField.MUSICBRAINZ_LYRICISTID, "MusicBrainz/Lyricist Id"),
    (BasicField.MUSICBRAINZ_MIXERID, "MusicBrainz/Mixer Id"),
    (BasicField.MUSICBRAINZ_ORIGINALALBUMID, "MusicBrainz/Original Album Id"),
    (BasicField.MUSICBRAINZ_ORIGINALARTISTID, "MusicBrainz/Original Artist Id"),
    (BasicField.MUSICBRAINZ_ORIGINALRELEASEID, "MusicBrainz/Original Release Id"),
    (BasicField.MUSICBRAINZ_PRODUCERID, "MusicBrainz/Producer Id"),
    (BasicField.MUSICBRAINZ_RELEASEARTISTID, "MusicBrainz/Release Artist Id"),
    (BasicField.MUSICBRAINZ_RELEASEGROUPID, "MusicBrainz/Release Group Id"),
    (BasicField.MUSICBRAINZ_RELEASETRACKID, "MusicBrainz/Release Track Id"),
    (BasicField.MUSICBRAINZ_REMIXERID, "MusicBrainz/Remixer Id"),
    (BasicField.MUSICBRAINZ_TRACKID, "MusicBrainz/Track Id"),
    (BasicField.MUSICBRAINZ_TRMID, "MusicBrainz/TRM Id"),
    (BasicField.MUSICBRAINZ_WORKID, "MusicBrainz/Work Id"),
    (BasicField.ORGANIZATION, "Publisher"),
    (BasicField.TITLE, "Title"),
    # WM/TrackNumber and WM/PartOfSet too but they are not 1:1
)

FIELD_TO_ASF_PROPERTY: Final = dict(BASIC_ASF_PROPERTIES)


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
    def get_fields(self) -> Tuple[Tuple[BasicField, Tuple[str, ...]], ...]:
        basic_fields: list[Tuple[BasicField, Tuple[str, ...]]] = []
        if self._file.tags:  # pyright: ignore[reportUnknownMemberType]
            asf_fields = self._ensure_tagged_asf()
            basic_fields.extend(
                (tag, tuple(self._property_to_text(p) for p in asf_fields[prop]))  # pyright: ignore[reportUnknownVariableType]
                for tag, prop in BASIC_ASF_PROPERTIES
                if prop in asf_fields
            )

            (track_number, track_total) = self._get_wm_tracknumber()
            if track_number:
                basic_fields.append((BasicField.TRACKNUMBER, (str(track_number),)))
            if track_total:
                basic_fields.append((BasicField.TRACKTOTAL, (str(track_total),)))

            (disc_number, disc_total) = self._get_wm_partofset()
            if disc_number is not None:
                basic_fields.append((BasicField.DISCNUMBER, (str(disc_number),)))
            if disc_total is not None:
                basic_fields.append((BasicField.DISCTOTAL, (str(disc_total),)))

        return tuple(basic_fields)

    @override
    def _set_field(self, field: BasicField | str, value: str | List[str] | None):
        if not isinstance(field, BasicField):
            raise ValueError("asf tagger only uses BasicField")
        fields = self._ensure_tagged_asf()
        if value is None:
            match field:
                case BasicField.DISCNUMBER:
                    (_, disc_total) = self._get_wm_partofset()
                    self._set_wm_partofset(None, disc_total)
                case BasicField.DISCTOTAL:
                    (disc_number, _) = self._get_wm_partofset()
                    self._set_wm_partofset(disc_number, None)
                case BasicField.RELEASECOUNTRY | BasicField.RELEASETYPE:
                    logger.warning(f"don't know how to remove {field.name} from ASF tag in {self._get_file().filename}")
                case BasicField.TRACKNUMBER:
                    (_, track_total) = self._get_wm_tracknumber()
                    self._set_wm_tracknumber(None, track_total)
                case BasicField.TRACKTOTAL:
                    (track_number, _) = self._get_wm_tracknumber()
                    self._set_wm_tracknumber(track_number, None)
                case BasicField.UNKNOWN:
                    pass
                case _:
                    del fields[FIELD_TO_ASF_PROPERTY[field]]
        else:
            value_list = value if isinstance(value, List) else [value]
            match field:
                case BasicField.COMPILATION:
                    if value_list and value_list[0]:
                        fields[FIELD_TO_ASF_PROPERTY[field]] = ["1"]
                    elif FIELD_TO_ASF_PROPERTY[field] in fields:
                        del fields[FIELD_TO_ASF_PROPERTY[field]]
                case BasicField.DISCNUMBER:
                    (_, disc_total) = self._get_wm_partofset()
                    self._set_wm_partofset(value_list[0] if value_list[0] else None, disc_total)
                case BasicField.DISCTOTAL:
                    (disc_number, _) = self._get_wm_partofset()
                    self._set_wm_partofset(disc_number, value_list[0] if value_list[0] else None)
                case BasicField.RELEASECOUNTRY | BasicField.RELEASETYPE:
                    raise ValueError(f"cannot set {field.name} in ASF tag on {self._get_file().filename}")
                case BasicField.TRACKNUMBER:
                    (_, track_total) = self._get_wm_tracknumber()
                    self._set_wm_tracknumber(value_list[0] if value_list[0] else None, track_total)
                case BasicField.TRACKTOTAL:
                    (track_number, _) = self._get_wm_tracknumber()
                    self._set_wm_tracknumber(track_number, value_list[0] if value_list[0] else None)
                case BasicField.UNKNOWN:
                    raise ValueError("cannot set tag value UNKNOWN")
                case _:
                    fields[FIELD_TO_ASF_PROPERTY[field]] = value_list

    def _ensure_tagged_asf(self) -> ASFTags:
        if self._file.tags is None:
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

        fields = self._ensure_tagged_asf()
        if value is None and "WM/PartOfSet" in fields:
            del fields["WM/PartOfSet"]
        elif value is not None and ("WM/PartOfSet" not in fields or fields["WM/PartOfSet"] != [value]):
            fields["WM/PartOfSet"] = [value]

    def _set_wm_tracknumber(self, track_number: str | None, track_total: str | None):
        if track_number is None and track_total is None:
            value = None
        elif track_total is None:
            value = track_number
        elif track_number is None:
            value = f"/{track_total}"
        else:
            value = f"{track_number}/{track_total}"

        fields = self._ensure_tagged_asf()
        if value is None and "WM/TrackNumber" in fields:
            del fields["WM/TrackNumber"]
        elif value is not None and ("WM/TrackNumber" not in fields or fields["WM/TrackNumber"] != [value]):
            fields["WM/TrackNumber"] = [value]
