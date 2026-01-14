import logging
import textwrap
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)


def make_tag_serializable(key: str, value):
    # TODO this is a hack! actually need to handle multi-value, images
    if key == "covr":
        return "binary data not stored"
    if isinstance(value, list) and len(value) > 0:
        return make_tag_serializable(key, value[0])
    if hasattr(value, "pprint"):
        return value.pprint()
    return textwrap.shorten(str(value), width=4096)


def get_stream_info(file: FLAC | MP3 | mutagen.FileType, codec: str | None):
    info = {}
    # maybe this isn't necessary but I don't think there's a guarantee that these attributes exist
    if hasattr(file.info, "length"):
        info |= {"length": file.info.length}
    else:
        logger.warning(f"couldn't determine stream length in {file.filename}")

    if hasattr(file.info, "bitrate"):
        info |= {"bitrate": file.info.bitrate}
    else:
        logger.warning(f"couldn't determine stream bitrate in {file.filename}")

    if hasattr(file.info, "channels"):
        info |= {"channels": file.info.channels}
    else:
        logger.warning(f"couldn't determine stream channels in {file.filename}")

    if hasattr(file.info, "sample_rate"):
        info |= {"sample_rate": file.info.sample_rate}
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
    info |= {"codec": codec}

    return info


def get_metadata(path: str):
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
        stream_info = get_stream_info(file, codec)
        tags = dict(((k, make_tag_serializable(k, v)) for k, v in file.tags.items()))

        # extract tracktotal from ID3 tags
        if str.count(tags.get("tracknumber", ""), "/") == 1:
            [tracknumber, tracktotal] = tags["tracknumber"].split("/")
            tags["tracknumber"] = tracknumber
            tags["tracktotal"] = tracktotal

        return (tags, stream_info)

    return None
