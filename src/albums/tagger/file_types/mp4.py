import logging
from copy import copy
from pathlib import Path
from typing import Callable, Final, Generator, List, Tuple, override

import av
from mutagen._tags import PaddingInfo
from mutagen.mp4 import MP4, AtomDataType, MP4Cover, MP4FreeForm, MP4Tags

from ...picture.scan import PictureScanner
from ..base_mutagen import AbstractMutagenTagger
from ..types import BasicTag, Picture, PictureType

logger: Final = logging.getLogger(__name__)


M4A_TEXT_FRAMES: Final[Tuple[Tuple[BasicTag, str], ...]] = (
    (BasicTag.ALBUM, "©alb"),
    (BasicTag.ALBUMSORT, "soal"),
    (BasicTag.ALBUMARTIST, "aART"),
    (BasicTag.ALBUMARTISTSORT, "soaa"),
    (BasicTag.ARTIST, "©ART"),
    (BasicTag.ARTISTSORT, "soar"),
    (BasicTag.TITLE, "©nam"),
    (BasicTag.GENRE, "©gen"),
    (BasicTag.ORGANIZATION, "©pub"),
)
M4A_BYTES_FRAMES: Final[Tuple[Tuple[BasicTag, str], ...]] = (
    (BasicTag.BARCODE, "----:com.apple.iTunes:BARCODE"),
    (BasicTag.MUSICBRAINZ_ALBUMARTISTID, "----:com.apple.iTunes:MusicBrainz Album Artist Id"),
    (BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY, "----:com.apple.iTunes:MusicBrainz Album Release Country"),
    (BasicTag.MUSICBRAINZ_ALBUMRELEASETYPE, "----:com.apple.iTunes:MusicBrainz Album Release Type"),
    (BasicTag.MUSICBRAINZ_ALBUMID, "----:com.apple.iTunes:MusicBrainz Album Id"),
    (BasicTag.MUSICBRAINZ_ARRANGERID, "----:com.apple.iTunes:MusicBrainz Arranger Id"),
    (BasicTag.MUSICBRAINZ_ARTISTID, "----:com.apple.iTunes:MusicBrainz Artist Id"),
    (BasicTag.MUSICBRAINZ_COMPOSERID, "----:com.apple.iTunes:MusicBrainz Composer Id"),
    (BasicTag.MUSICBRAINZ_CONDUCTORID, "----:com.apple.iTunes:MusicBrainz Conductor Id"),
    (BasicTag.MUSICBRAINZ_DIRECTORID, "----:com.apple.iTunes:MusicBrainz Director Id"),
    (BasicTag.MUSICBRAINZ_DISCID, "----:com.apple.iTunes:MusicBrainz Disc Id"),
    (BasicTag.MUSICBRAINZ_LYRICISTID, "----:com.apple.iTunes:MusicBrainz Lyricist Id"),
    (BasicTag.MUSICBRAINZ_MIXERID, "----:com.apple.iTunes:MusicBrainz Mixer Id"),
    (BasicTag.MUSICBRAINZ_ORIGINALALBUMID, "----:com.apple.iTunes:MusicBrainz Original Album Id"),
    (BasicTag.MUSICBRAINZ_ORIGINALARTISTID, "----:com.apple.iTunes:MusicBrainz Original Artist Id"),
    (BasicTag.MUSICBRAINZ_ORIGINALRELEASEID, "----:com.apple.iTunes:MusicBrainz Original Release Id"),
    (BasicTag.MUSICBRAINZ_PRODUCERID, "----:com.apple.iTunes:MusicBrainz Producer Id"),
    (BasicTag.MUSICBRAINZ_TRACKID, "----:com.apple.iTunes:MusicBrainz Track Id"),
    (BasicTag.MUSICBRAINZ_TRMID, "----:com.apple.iTunes:MusicBrainz TRM Id"),
    (BasicTag.MUSICBRAINZ_RELEASEARTISTID, " ----:com.apple.iTunes:MusicBrainz Release Artist Id"),
    (BasicTag.MUSICBRAINZ_RELEASEGROUPID, " ----:com.apple.iTunes:MusicBrainz Release Group Id"),
    (BasicTag.MUSICBRAINZ_RELEASETRACKID, "----:com.apple.iTunes:MusicBrainz Release Track Id"),
    (BasicTag.MUSICBRAINZ_REMIXERID, "----:com.apple.iTunes:MusicBrainz Remixer Id"),
    (BasicTag.MUSICBRAINZ_WORKID, "----:com.apple.iTunes:MusicBrainz Work Id"),
)
# cpil, disk and trkn too but they are not text or text-as-bytes

TAG_TO_M4A_TEXT_FRAME = dict(M4A_TEXT_FRAMES)
TAG_TO_M4A_BYTES_FRAME = dict(M4A_BYTES_FRAMES)
_TAG_CPIL = dict(((BasicTag.COMPILATION, "cpil"),))  # so that type of TAG_TO_M4A_FRAME will be dict[Literal[...] ...]
TAG_TO_M4A_FRAME = TAG_TO_M4A_BYTES_FRAME | TAG_TO_M4A_TEXT_FRAME | _TAG_CPIL  # trkn and disk are not 1:1


class Mp4Tagger(AbstractMutagenTagger[MP4]):
    _file: MP4
    _picture_scanner: PictureScanner
    _has_video: bool

    def __init__(self, path: Path, picture_scanner: PictureScanner, padding: Callable[[PaddingInfo], int]):
        super().__init__(padding)
        self._has_video = str.lower(path.suffix) == ".mp4" and _mp4_has_video(path)
        self._file = MP4(path)
        self._picture_scanner = picture_scanner

    @override
    def has_video(self) -> bool:
        return self._has_video

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
        if new_picture.picture_info.mime_type == "image/jpeg":
            imageformat = MP4Cover.FORMAT_JPEG
        elif new_picture.picture_info.mime_type == "image/png":
            imageformat = MP4Cover.FORMAT_PNG
        else:
            raise ValueError(f"unsupported MIME type {new_picture.picture_info.mime_type} for saving in covr tag")
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
    def get_tags(self) -> Tuple[Tuple[BasicTag, Tuple[str, ...]], ...]:
        basic_tags: list[Tuple[BasicTag, Tuple[str, ...]]] = []
        if self._file.tags:  # pyright: ignore[reportUnknownMemberType]
            tags = self._ensure_tags()
            basic_tags.extend((tag, tuple(tags[atom])) for tag, atom in M4A_TEXT_FRAMES if atom in tags)  # pyright: ignore[reportUnknownArgumentType]
            basic_tags.extend((tag, tuple(v.decode("utf-8") for v in tags[atom])) for tag, atom in M4A_BYTES_FRAMES if atom in tags)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
            if "cpil" in tags and tags["cpil"]:
                basic_tags.append((BasicTag.COMPILATION, ("1",)))

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

        # TODO also load legacy "gnre" value with id3v1 genre number

        return tuple(basic_tags)

    @override
    def _set_tag(self, tag: BasicTag, value: str | List[str] | None):
        tags = self._ensure_tags()

        if value is None:
            match tag:
                case BasicTag.DISCNUMBER:
                    (_, disc_total) = self._get_disk()
                    self._set_disk(None, disc_total)
                case BasicTag.DISCTOTAL:
                    (disc_number, _) = self._get_disk()
                    self._set_disk(disc_number, None)
                case (
                    BasicTag.OLD_ALBUM_ARTIST
                    | BasicTag.OLD_LABEL
                    | BasicTag.OLD_PUBLISHER
                    | BasicTag.OLD_TOTAL_DISCS
                    | BasicTag.RELEASECOUNTRY
                    | BasicTag.RELEASETYPE
                ):
                    logger.warning(f"don't know how to remove {tag.name} from MP4 tag in {self._get_file().filename}")
                case BasicTag.TRACKNUMBER:
                    (_, track_total) = self._get_trkn()
                    self._set_trkn(None, track_total)
                case BasicTag.TRACKTOTAL:
                    (track_number, _) = self._get_trkn()
                    self._set_trkn(track_number, None)
                case _:
                    del tags[TAG_TO_M4A_FRAME[tag]]
        else:
            value_list = value if isinstance(value, List) else [value]
            match tag:
                case BasicTag.COMPILATION:
                    if value_list and value_list[0]:
                        tags["cpil"] = ["1"]
                    elif "cpil" in tags:
                        del tags["cpil"]
                case BasicTag.DISCNUMBER:
                    (_, disc_total) = self._get_disk()
                    self._set_disk(int(value_list[0]) if value_list[0] else None, disc_total)
                case BasicTag.DISCTOTAL:
                    (disc_number, _) = self._get_disk()
                    self._set_disk(disc_number, int(value_list[0]) if value_list[0] else None)
                case (
                    BasicTag.OLD_ALBUM_ARTIST
                    | BasicTag.OLD_LABEL
                    | BasicTag.OLD_PUBLISHER
                    | BasicTag.OLD_TOTAL_DISCS
                    | BasicTag.RELEASECOUNTRY
                    | BasicTag.RELEASETYPE
                ):
                    raise ValueError(f"cannot set {tag.name} in MP4 tag on {self._get_file().filename}")
                case BasicTag.TRACKNUMBER:
                    (_, track_total) = self._get_trkn()
                    self._set_trkn(int(value_list[0]) if value_list[0] else None, track_total)
                case BasicTag.TRACKTOTAL:
                    (track_number, _) = self._get_trkn()
                    self._set_trkn(track_number, int(value_list[0]) if value_list[0] else None)
                case _:
                    if tag in TAG_TO_M4A_BYTES_FRAME:
                        prop = TAG_TO_M4A_BYTES_FRAME[tag]  # type: ignore
                        tags[prop] = [MP4FreeForm(v.encode("utf-8"), AtomDataType.UTF8) for v in value_list]
                    else:
                        prop = TAG_TO_M4A_TEXT_FRAME[tag]  # pyright: ignore[reportArgumentType]
                        tags[prop] = value_list

    def _ensure_tags(self) -> MP4Tags:
        if self._file.tags is None:
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


def _mp4_has_video(path: Path) -> bool:
    with av.open(path) as container:
        return len(container.streams.video) > 0
