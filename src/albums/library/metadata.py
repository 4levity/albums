from dataclasses import dataclass
import logging
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


def get_metadata(path: str) -> tuple[dict, Stream]:
    (file, codec, capabilities) = _mutagen_load_file(path)
    if file is not None:
        stream_info = _get_stream_info(file, codec)
        tags = _get_tags(file)
        return (tags, stream_info)

    return None


def album_is_basic_taggable(album: Album):  # TODO use TagCapabilities instead
    ok = True
    for track in album.tracks:
        if not supports_basic_tags(track.filename, track.stream.codec if track.stream else None):
            ok = False
    return ok


def supports_basic_tags(filename: str, codec: str):  # TODO use TagCapabilities instead
    return str.lower(Path(filename).suffix) in [".flac", ".mp3", ".ogg"] and (codec is None or codec in ["FLAC", "MP3", "Ogg Vorbis"])


def set_basic_tags(path: str, values: list[tuple[str, str | None]]):
    # remove any tag, only set supported tags
    for name, value in values:
        if value is not None and name not in BASIC_TAGS:
            raise ValueError(f"tag '{name}' is not a supported basic tag")

    (file, codec, capabilities) = _mutagen_load_file(path)
    if not supports_basic_tags(path, codec):  # TODO use TagCapabilities instead
        logger.warning(f"cannot set tags {[name for (name, value) in values]} in {codec} file {path}")
        return False

    changed = False
    for name, value in values:
        if name == "tracktotal" and not capabilities.has_tracktotal:
            changed |= _set_tracktotal_in_tracknumber(file, value)
        elif name == "disctotal" and not capabilities.has_disctotal:
            changed |= _set_disctotal_in_discnumber(file, value)
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


def _set_disctotal_in_discnumber(file: FLAC | MP3 | mutagen.FileType, value: str | None):
    discnumbers = file["discnumber"] if "discnumber" in file else None
    if discnumbers and len(discnumbers) > 1:  # unlikely, we are probably only doing this for MP3 files
        logger.warning(f"more than one discnumber tag, ignoring all but first: {discnumbers}")

    if value is None:
        if discnumbers and "/" in discnumbers[0]:
            file["discnumber"] = f"{discnumbers[0].split('/')[0]}"  # remove / and anything after
            file.save()
            return True
        else:
            logger.debug("not removing disctotal because there is no discnumber tag to remove it from")
    elif "discnumber" not in file:
        logger.warning("failed to set disctotal because there is no discnumber tag")
    else:
        file["discnumber"] = f"{discnumbers[0].split('/')[0]}/{value}"
        file.save()
        return True
    return False


def _set_tracktotal_in_tracknumber(file: FLAC | MP3 | mutagen.FileType, value: str | None):
    tracknumbers = file["tracknumber"] if "tracknumber" in file else None
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
    else:
        file["tracknumber"] = f"{tracknumbers[0].split('/')[0]}/{value}"
        file.save()
        return True
    return False


def _mutagen_load_file(path: str) -> tuple[FLAC | MP3 | mutagen.FileType, str, TagCapabilities]:
    codec: str | None = None
    suffix = str.lower(path.suffix)
    if suffix == ".flac":
        file = FLAC(path)
        codec = "FLAC"
        capabilities = TagCapabilities(has_tracktotal=True, has_disctotal=True)
    elif suffix == ".mp3":
        file = MP3(path, ID3=EasyID3)  # limited tags, converted to canonical names
        codec = "MP3"
        capabilities = TagCapabilities(has_tracktotal=False, has_disctotal=False)
    else:
        file = mutagen.File(path)
        codec = _get_codec(file)
        capabilities = TagCapabilities(has_tracktotal=True, has_disctotal=True)  # TODO this is often NOT true

    return (file, codec, capabilities)


def _get_tags(file: FLAC | MP3 | mutagen.FileType):
    def store_value(key: str, value):
        if key == "covr":
            return "binary data not stored"  # TODO: get image metadata
        if hasattr(value, "pprint"):
            return str(value.pprint())
        return textwrap.shorten(str(value), width=4096)

    tags: dict[str, list[str]] = {}
    for tag_name, tag_value in file.tags.items():
        name = str.lower(tag_name)
        for value in tag_value if isinstance(tag_value, list) else [tag_value]:
            tags.setdefault(name, []).append(store_value(name, value))
    return tags


def _get_codec(file: FLAC | MP3 | mutagen.FileType) -> str:
    if hasattr(file.info, "codec_name"):
        return f"{file.info.codec_name}"
    if hasattr(file.info, "codec"):
        return f"{file.info.codec}"
    if hasattr(file.info, "pprint"):
        return file.info.pprint().split(",")[0]
    logger.warning(f"couldn't determine codec in {file.filename}")
    return "unknown"


def _get_stream_info(file: FLAC | MP3 | mutagen.FileType, codec: str | None) -> Stream:
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
        stream.channel = file.info.channels
    else:
        logger.warning(f"couldn't determine stream channels in {file.filename}")

    if hasattr(file.info, "sample_rate"):
        stream.sample_rate = file.info.sample_rate
    else:
        logger.warning(f"couldn't determine stream sample rate in {file.filename}")

    stream.codec = codec

    return stream
