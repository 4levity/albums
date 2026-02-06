import logging
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture
from mutagen.mp3 import MP3

from ..types import Album, Picture, PictureType, Stream

logger = logging.getLogger(__name__)
BASIC_TAGS = {"artist", "album", "title", "albumartist", "tracknumber", "tracktotal", "discnumber", "disctotal"}


@dataclass
class TagCapabilities:
    has_tracktotal: bool
    has_disctotal: bool


class MutagenFileTypeLike(dict[Any, Any]):
    # a type to resemble mutagen FileType objects including FLAC, MP3 and whatever mutagen.File returns
    filename: str
    info: Any
    tags: dict[str, Any]

    def save(self): ...


def get_metadata(path: Path) -> tuple[dict[Any, Any], Stream, list[Picture]] | None:
    file_info = _mutagen_load_file(path)
    if not file_info:
        return None

    (file, codec, capabilities) = file_info
    stream_info = _get_stream_info(file, codec)
    tags = _get_tags(file, capabilities)
    pictures = _get_pictures(file)
    return (tags, stream_info, pictures)


def album_is_basic_taggable(album: Album):  # TODO use TagCapabilities instead
    ok = True
    for track in album.tracks:
        if not supports_basic_tags(Path(track.filename), track.stream.codec if track.stream else None):
            ok = False
    return ok


def supports_basic_tags(filename: Path, codec: str | None):  # TODO use TagCapabilities instead
    return str.lower(filename.suffix) in [".flac", ".mp3", ".ogg"] and (codec is None or codec in ["FLAC", "MP3", "Ogg Vorbis"])


def set_basic_tags(path: Path, tag_values: list[tuple[str, str | list[str] | None]]):
    # remove any tag, only set supported tags
    for name, value in tag_values:
        if value is not None and name not in BASIC_TAGS:
            raise ValueError(f"tag '{name}' is not a supported basic tag")

    file_info = _mutagen_load_file(path)
    if not file_info:
        raise ValueError(f"couldn't access {path} to write tags")

    (file, codec, capabilities) = file_info
    if not supports_basic_tags(path, codec):  # TODO use TagCapabilities instead
        logger.warning(f"cannot set tags {[name for (name, _) in tag_values]} in {codec} file {path}")
        return False

    changed = False
    for name, value in tag_values:
        if (name in {"tracknumber", "tracktotal"} and not capabilities.has_tracktotal) or (
            name in {"discnumber", "disctotal"} and not capabilities.has_disctotal
        ):
            tags = _get_tags(file, capabilities)
            new_value = value[0] if isinstance(value, list) else value
            if name == "tracknumber":
                changed |= _set_tracknumber_and_tracktotal(file, new_value, tags.get("tracktotal", [None])[0])
            if name == "tracktotal":
                changed |= _set_tracknumber_and_tracktotal(file, tags.get("tracknumber", [None])[0], new_value)
            if name == "discnumber":
                changed |= _set_discnumber_and_disctotal(file, new_value, tags.get("disctotal", [None])[0])
            if name == "disctotal":
                changed |= _set_discnumber_and_disctotal(file, tags.get("discnumber", [None])[0], new_value)
        elif value is None:
            if name in file:
                del file[name]
                changed = True
        else:
            file[name] = value
            changed = True

    if changed:
        file.save()
        return True
    return False


def _set_discnumber_and_disctotal(file: MutagenFileTypeLike, discnumber: str | None, disctotal: str | None):
    if discnumber is None and disctotal is None:
        value = None
    elif disctotal is None:
        value = discnumber
    elif discnumber is None:
        value = f"/{disctotal}"
    else:
        value = f"{discnumber}/{disctotal}"

    if value is None and "discnumber" in file:
        del file["discnumber"]
        return True

    if value is not None and ("discnumber" not in file or file["discnumber"] != [value]):
        file["discnumber"] = value
        return True

    return False


def _set_tracknumber_and_tracktotal(file: MutagenFileTypeLike, tracknumber: str | None, tracktotal: str | None):
    if tracknumber is None and tracktotal is None:
        value = None
    elif tracktotal is None:
        value = tracknumber
    elif tracknumber is None:
        value = f"/{tracktotal}"
    else:
        value = f"{tracknumber}/{tracktotal}"

    if value is None and "tracknumber" in file:
        del file["tracknumber"]
        return True

    if value is not None and ("tracknumber" not in file or file["tracknumber"] != [value]):
        file["tracknumber"] = value
        return True

    return False


def _mutagen_load_file(path: Path) -> tuple[MutagenFileTypeLike, str, TagCapabilities] | None:
    codec: str | None = None
    suffix = str.lower(path.suffix)
    if suffix == ".flac":
        file = FLAC(path)  # pyright: ignore[reportAssignmentType]
        codec = "FLAC"
        capabilities = TagCapabilities(has_tracktotal=True, has_disctotal=True)
    elif suffix == ".mp3":
        file = MP3(path, ID3=EasyID3)  # pyright: ignore[reportAssignmentType]
        codec = "MP3"
        capabilities = TagCapabilities(has_tracktotal=False, has_disctotal=False)
    else:
        file: MutagenFileTypeLike | None = mutagen.File(  # pyright: ignore[reportPrivateImportUsage, reportUnknownMemberType, reportAssignmentType]
            path
        )
        if file is None:
            return None
        codec = _get_codec(file)
        capabilities = TagCapabilities(has_tracktotal=True, has_disctotal=True)  # TODO this is often NOT true

    if file is not None:
        return (file, codec, capabilities)
    else:
        return None


def _get_tags(file: MutagenFileTypeLike, capabilities: TagCapabilities):
    def store_value(key: str, value: Any):
        if key == "covr":
            return "binary data not stored"  # TODO: get image metadata
        if hasattr(value, "pprint"):
            return str(value.pprint())
        return textwrap.shorten(str(value), width=4096)

    tags: dict[str, list[str]] = {}
    for tag_name, tag_value in file.tags.items():
        name = str.lower(tag_name)
        for value in tag_value if isinstance(tag_value, list) else [tag_value]:  # pyright: ignore[reportUnknownVariableType]
            tags.setdefault(name, []).append(store_value(name, value))
    _normalize(tags, capabilities)
    return tags


def _normalize(tags: dict[str, list[str]], capabilities: TagCapabilities) -> None:
    tracknumber_tag = tags.get("tracknumber", [None])[0]
    if not capabilities.has_tracktotal:
        if "tracktotal" in tags:
            logger.warning("internal error: tracktotal tag exists but capabilities indicate it should not")
        # extract tracktotal from ID3/etc tags
        elif tracknumber_tag and str.count(tracknumber_tag, "/") == 1:
            [tracknumber, tracktotal] = tracknumber_tag.split("/")
            tags["tracknumber"] = [tracknumber]
            tags["tracktotal"] = [tracktotal]

    if not capabilities.has_disctotal:
        if "disctotal" in tags:
            logger.warning("internal error: disctotal tag exists but capabilities indicate it should not")
        # extract disctotal from ID3 tags
        discnumber_tag = tags.get("discnumber", [None])[0]
        if discnumber_tag and "disctotal" not in tags and str.count(discnumber_tag, "/") == 1:
            [discnumber, disctotal] = discnumber_tag.split("/")
            tags["discnumber"] = [discnumber]
            tags["disctotal"] = [disctotal]


def _get_codec(file: MutagenFileTypeLike) -> str:
    if hasattr(file.info, "codec_name"):
        return f"{file.info.codec_name}"
    if hasattr(file.info, "codec"):
        return f"{file.info.codec}"
    if hasattr(file.info, "pprint"):
        return file.info.pprint().split(",")[0]
    logger.warning(f"couldn't determine codec in {file.filename}")
    return "unknown"


def _get_stream_info(file: MutagenFileTypeLike, codec: str) -> Stream:
    stream = Stream()
    # maybe this isn't necessary but I don't think there's a guarantee that these attributes exist
    if hasattr(file.info, "length"):
        stream.length = file.info.length
    else:
        logger.warning(f"couldn't determine stream length in {file.filename}")

    if hasattr(file.info, "bitrate"):
        stream.bitrate = file.info.bitrate
    else:
        logger.warning(f"couldn't determine stream bitrate in {file.filename}")

    if hasattr(file.info, "channels"):
        stream.channels = file.info.channels
    else:
        logger.warning(f"couldn't determine stream channels in {file.filename}")

    if hasattr(file.info, "sample_rate"):
        stream.sample_rate = file.info.sample_rate
    else:
        logger.warning(f"couldn't determine stream sample rate in {file.filename}")

    stream.codec = codec

    return stream


def _get_pictures(file: MutagenFileTypeLike) -> list[Picture]:
    pictures: list[Picture] = []
    if isinstance(file, FLAC):
        pictures = _get_flac_pictures(file.pictures)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
    return pictures


def _get_flac_pictures(flac_pictures: list[FlacPicture]) -> list[Picture]:
    pictures: list[Picture] = []
    for picture in flac_pictures:
        # TODO: image info in the metadata block can be wrong, we should check against image data so we can offer to fix it
        pictures.append(
            Picture(
                PictureType(picture.type),
                str(picture.mime) if isinstance(picture.mime, str) else "Unknown",  # type: ignore
                picture.width,
                picture.height,
                len(picture.data) if picture.data else 0,  # type: ignore
            )
        )
    return pictures
