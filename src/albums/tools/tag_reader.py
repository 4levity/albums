import logging
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from pathlib import Path


logger = logging.getLogger(__name__)


def make_tag_serializable(value):
    # TODO this is a hack! actually need to handle multi-value, images
    if isinstance(value, list) and len(value) > 0:
        return make_tag_serializable(value[0])
    elif hasattr(value, "pprint"):
        return value.pprint()
    else:
        return str(value)


def get_metadata(cwd: str, relpaths: list[str]):
    tags = []
    for relpath in relpaths:
        path = Path(cwd) / relpath
        suffix = str.lower(path.suffix)
        if suffix == ".flac":
            file = FLAC(path)
        elif suffix == ".mp3":
            file = MP3(path, ID3=EasyID3)  # limited tags, converted to canonical names
        else:
            file = mutagen.File(path)

        if file is not None:
            item = {"SourceFile": relpath}
            for name, value in file.tags.items():
                # TODO filter useless tags
                item[name] = make_tag_serializable(value)
            tags.append(item)
    return tags
