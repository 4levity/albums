from dataclasses import dataclass
import logging
from typing import Any
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from pathlib import Path
import textwrap

from ..types import Album, Stream


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


def get_metadata(path: Path) -> tuple[dict[Any, Any], Stream] | None:
    file_info = _mutagen_load_file(path)
    if not file_info:
        return None

    (file, codec, capabilities) = file_info
    stream_info = _get_stream_info(file, codec)
    tags = _get_tags(file, capabilities)
    return (tags, stream_info)


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
        if name == "tracktotal" and not capabilities.has_tracktotal:
            changed |= _set_tracktotal_in_tracknumber(file, value[0] if isinstance(value, list) else value)
        elif name == "disctotal" and not capabilities.has_disctotal:
            changed |= _set_disctotal_in_discnumber(file, value[0] if isinstance(value, list) else value)
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


def _set_disctotal_in_discnumber(file: MutagenFileTypeLike, value: str | None):
    old_discnumbers: list[str] | None = file["discnumber"] if "discnumber" in file else None
    if old_discnumbers and len(old_discnumbers) > 1:  # unlikely, we are probably only doing this for MP3 files
        logger.warning(f"more than one discnumber tag, ignoring all but first: {old_discnumbers}")

    if value is None:
        if old_discnumbers and "/" in old_discnumbers[0]:
            file["discnumber"] = f"{old_discnumbers[0].split('/')[0]}"  # remove / and anything after
            file.save()
            return True
        else:
            logger.debug("not removing disctotal because there is no discnumber tag to remove it from")
    elif "discnumber" not in file:
        logger.warning("failed to set disctotal because there is no discnumber tag")
    elif old_discnumbers and len(old_discnumbers) > 0:  # old_discnumbers is definitely a non-empty array here, added checks for pyright
        file["discnumber"] = f"{old_discnumbers[0].split('/')[0]}/{value}"
        file.save()
        return True
    return False


def _set_tracktotal_in_tracknumber(file: MutagenFileTypeLike, value: str | None):
    tracknumbers: list[str] | None = file["tracknumber"] if "tracknumber" in file else None
    if tracknumbers and len(tracknumbers) > 1:  # unlikely, we are probably only doing this for MP3 files
        logger.warning(f"more than one tracknumber tag, ignoring all but first: {tracknumbers}")

    if value is None:
        if tracknumbers and "/" in tracknumbers[0]:
            file["tracknumber"] = f"{tracknumbers[0].split('/')[0]}"  # remove / and anything after
            file.save()
            return True
        else:
            logger.debug("not removing tracktotal because there is no tracknumber tag to remove it from")
    elif "tracknumber" not in file:
        logger.warning("failed to set tracktotal because there is no tracknumber tag")
    elif tracknumbers and len(tracknumbers) > 0:  # tracknumbers is definitely a non-empty array here, added checks for pyright
        file["tracknumber"] = f"{tracknumbers[0].split('/')[0]}/{value}"
        file.save()
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
        file: MutagenFileTypeLike | None = mutagen.File(path)  # pyright: ignore[reportPrivateImportUsage, reportUnknownMemberType, reportAssignmentType]
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
