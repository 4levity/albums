import logging
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3


logger = logging.getLogger(__name__)


def make_tag_serializable(value):
    # TODO this is a hack! actually need to handle multi-value, images
    if isinstance(value, list) and len(value) > 0:
        return make_tag_serializable(value[0])
    elif hasattr(value, "pprint"):
        return value.pprint()
    else:
        return str(value)


def stream_info(file: FLAC | MP3 | mutagen.FileType):
    info = {}
    # maybe this isn't necessary but I don't think there's a guarantee that these attributes exist
    try:
        info |= {"length": file.info.length}
    except AttributeError:
        logger.warning(f"couldn't determine stream length in {file.filename}")

    try:
        info |= {"bitrate": file.info.bitrate}
    except AttributeError:
        logger.warning(f"couldn't determine stream bitrate in {file.filename}")

    try:
        info |= {"channels": file.info.channels}
    except AttributeError:
        logger.warning(f"couldn't determine stream channels in {file.filename}")

    try:
        info |= {"sample_rate": file.info.sample_rate}
    except AttributeError:
        logger.warning(f"couldn't determine stream sample rate in {file.filename}")

    return info


def get_metadata(path: str):
    suffix = str.lower(path.suffix)
    if suffix == ".flac":
        file = FLAC(path)
    elif suffix == ".mp3":
        file = MP3(path, ID3=EasyID3)  # limited tags, converted to canonical names
    else:
        file = mutagen.File(path)

    if file is not None:
        tags = dict(((k, make_tag_serializable(v)) for k, v in file.tags.items()))

        # extract tracktotal from ID3 tags
        if str.count(tags.get("tracknumber", ""), "/") == 1:
            [tracknumber, tracktotal] = tags["tracknumber"].split("/")
            tags["tracknumber"] = tracknumber
            tags["tracktotal"] = tracktotal

        return (tags, stream_info(file))

    return None
