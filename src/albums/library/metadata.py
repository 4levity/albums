import logging
import textwrap
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

from ..types import Stream


logger = logging.getLogger(__name__)


def get_metadata(path: str) -> tuple[dict, Stream]:
    codec: str | None = None
    suffix = str.lower(path.suffix)
    if suffix == ".flac":
        file = FLAC(path)
        codec = "FLAC"
    elif suffix == ".mp3":
        file = MP3(path, ID3=EasyID3)  # limited tags, converted to canonical names
        codec = "MP3"
    else:
        file = mutagen.File(path)

    if file is not None:
        stream_info = _get_stream_info(file, codec)
        tags = _get_tags(file)
        return (tags, stream_info)

    return None


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

    if not codec and hasattr(file.info, "codec_name"):
        codec = f"{file.info.codec_name}"
    elif not codec and hasattr(file.info, "codec"):
        codec = f"{file.info.codec}"
    elif not codec and hasattr(file.info, "pprint"):
        codec = file.info.pprint().split(",")[0]
    elif not codec:
        logger.warning(f"couldn't determine codec in {file.filename}")
        codec = "unknown"
    stream.codec = codec

    return stream
