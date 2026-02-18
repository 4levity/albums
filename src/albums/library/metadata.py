import base64
import io
import logging
import mimetypes
import textwrap
from copy import copy
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, Sequence, Tuple

import mutagen
import xxhash
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC, TALB, TIT2, TPE1, TPE2, TPOS, TRCK
from mutagen.id3._specs import Encoding
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
from PIL import Image, UnidentifiedImageError

from ..types import Album, Picture, PictureType, Stream

type PictureCache = Dict[Tuple[int, bytes], Picture]

logger = logging.getLogger(__name__)

BASIC_TAGS = {"artist", "album", "title", "albumartist", "tracknumber", "tracktotal", "discnumber", "disctotal"}
BASIC_TO_ID3 = {
    "artist": "tpe1",
    "album": "talb",
    "title": "tit2",
    "albumartist": "tpe2",
    "composer": "tcom",
    "genre": "tcon",
    "encoder": "tenc",
    "date": "tdrc",  # maybe this should be recordingdate
}  # TRCK and TPOS too but they are not 1:1
PROCESSED_ID3_TAGS = set(list(BASIC_TO_ID3.values()) + ["trck", "tpos", "apic", "covr"])


class TagType(Enum):
    VORBIS_COMMENTS = auto()
    ID3_FRAMES = auto()  # basic tags will be converted to Vorbis comment convention
    OTHER = auto()  # TODO more


class MutagenFileTypeLike(dict[Any, Any]):
    # a type to resemble mutagen FileType objects including FLAC, MP3 and whatever mutagen.File returns
    filename: str
    info: Any
    tags: Any

    def save(self, **_: Any): ...


def get_metadata(path: Path, picture_cache: PictureCache = {}) -> tuple[dict[Any, Any], Stream, list[Picture]] | None:
    file_info = _mutagen_load_file(path)
    if not file_info:
        return None

    (file, codec, tag_type) = file_info
    stream_info = _get_stream_info(file, codec)
    tags = _get_tags(file, tag_type)
    pictures = list(picture for (picture, _) in _get_pictures(file, picture_cache))
    return (tags, stream_info, pictures)


def get_embedded_image_data(path: Path) -> list[bytes]:
    file_info = _mutagen_load_file(path)
    if not file_info:
        return []
    (file, _, _) = file_info
    if isinstance(file, FLAC):
        return [flac_picture.data for flac_picture in file.pictures]  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    if isinstance(file, OggVorbis):
        return [flac_picture.data for flac_picture in _get_metadata_picture_blocks_from_ogg_vorbis(file)]  # pyright: ignore[reportUnknownMemberType]
    if isinstance(file, MP3):
        return [frame.data for frame in file.tags.getall("APIC")]
    return []


def album_is_basic_taggable(album: Album):  # TODO use TagType instead
    return all(supports_basic_tags(Path(track.filename), track.stream.codec if track.stream else None) for track in album.tracks)


def supports_basic_tags(filename: Path, codec: str | None):  # TODO use TagType instead
    return str.lower(filename.suffix) in [".flac", ".mp3", ".ogg"] and (codec is None or codec in ["FLAC", "MP3", "Ogg Vorbis"])


def set_basic_tags(path: Path, tag_values: list[tuple[str, str | list[str] | None]]):
    file_info = _mutagen_load_file(path)
    if not file_info:
        raise ValueError(f"couldn't access {path} to write tags")

    (file, _, tag_type) = file_info
    return set_basic_tags_file(file, tag_values, tag_type)


def set_basic_tags_file(file: MutagenFileTypeLike, tag_values: list[tuple[str, str | list[str] | None]], tag_type: TagType) -> bool:
    for name, _ in tag_values:
        # remove any tag, only set supported tags
        # if value is not None and name not in BASIC_TAGS:
        if name not in BASIC_TAGS:
            raise ValueError(f"tag '{name}' is not a supported basic tag")

    changed = False
    for name, value in tag_values:
        if tag_type == TagType.ID3_FRAMES:
            if not file.tags:
                file.tags = ID3()
            if name in {"tracknumber", "tracktotal", "discnumber", "disctotal"}:
                tags = _get_tags(file, tag_type)
                new_value = value[0] if isinstance(value, list) else value
                if name == "tracknumber":
                    changed |= _id3_set_tracknumber_and_tracktotal(file, new_value, tags.get("tracktotal", [None])[0])
                if name == "tracktotal":
                    changed |= _id3_set_tracknumber_and_tracktotal(file, tags.get("tracknumber", [None])[0], new_value)
                if name == "discnumber":
                    changed |= _id3_set_discnumber_and_disctotal(file, new_value, tags.get("disctotal", [None])[0])
                if name == "disctotal":
                    changed |= _id3_set_discnumber_and_disctotal(file, tags.get("discnumber", [None])[0], new_value)
            elif name == "artist":
                tpe1 = TPE1(encoding=Encoding.UTF8, text=value if isinstance(value, list) else [value])
                if "TPE1" in file.tags:
                    file.tags["TPE1"] = tpe1
                else:
                    file.tags.add(tpe1)
                changed = True
            elif name == "albumartist":
                tpe2 = TPE2(encoding=Encoding.UTF8, text=value if isinstance(value, list) else [value])
                if "TPE2" in file.tags:
                    file.tags["TPE2"] = tpe2
                else:
                    file.tags.add(tpe2)
                changed = True
            elif name == "album":
                talb = TALB(encoding=Encoding.UTF8, text=value if isinstance(value, list) else [value])
                if "TALB" in file.tags:
                    file.tags["TALB"] = talb
                else:
                    file.tags.add(talb)
                changed = True
            elif name == "title":
                tit2 = TIT2(encoding=Encoding.UTF8, text=value if isinstance(value, list) else [value])
                if "TIT2" in file.tags:
                    file.tags["TIT2"] = tit2
                else:
                    file.tags.add(tit2)
                changed = True
            else:
                logger.error(f"cannot set ID3 tag for {name}")  # shouldn't happen, not in BASIC_TAGS?

        else:
            if tag_type != TagType.VORBIS_COMMENTS:
                logger.warning(f"setting maybe unsupported tag {name} in {tag_type} file {file.filename}")
            if value is None:
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


def _id3_set_discnumber_and_disctotal(file: MutagenFileTypeLike, discnumber: str | None, disctotal: str | None):
    if discnumber is None and disctotal is None:
        value = None
    elif disctotal is None:
        value = discnumber
    elif discnumber is None:
        value = f"/{disctotal}"
    else:
        value = f"{discnumber}/{disctotal}"

    if value is None and "TPOS" in file:
        del file["TPOS"]
        return True

    if value is not None and "TPOS" not in file:
        file.tags.add(TPOS(encoding=Encoding.UTF8, text=[value]))
        return True
    elif value is not None and file["TPOS"].text != [value]:
        file["TPOS"] = TPOS(encoding=Encoding.UTF8, text=[value])
        return True

    return False


def _id3_set_tracknumber_and_tracktotal(file: MutagenFileTypeLike, tracknumber: str | None, tracktotal: str | None):
    if tracknumber is None and tracktotal is None:
        value = None
    elif tracktotal is None:
        value = tracknumber
    elif tracknumber is None:
        value = f"/{tracktotal}"
    else:
        value = f"{tracknumber}/{tracktotal}"

    if value is None and "TRCK" in file:
        del file["TRCK"]
        return True

    if value is not None and "TRCK" not in file:
        file.tags.add(TRCK(encoding=Encoding.UTF8, text=[value]))
        return True
    elif value is not None and file["TRCK"].text != [value]:
        file["TRCK"] = TRCK(encoding=Encoding.UTF8, text=[value])
        return True

    return False


def _mutagen_load_file(path: Path) -> tuple[MutagenFileTypeLike, str, TagType] | None:
    codec: str | None = None
    suffix = str.lower(path.suffix)
    if suffix == ".flac":
        file = FLAC(path)  # pyright: ignore[reportAssignmentType]
        codec = "FLAC"
        tag_type = TagType.VORBIS_COMMENTS
    elif suffix == ".mp3":
        file = MP3(path)  # pyright: ignore[reportAssignmentType]
        codec = "MP3"
        tag_type = TagType.ID3_FRAMES
    elif suffix == ".ogg":
        file = OggVorbis(path)  # pyright: ignore[reportAssignmentType]
        tag_type = TagType.VORBIS_COMMENTS
    else:
        file: MutagenFileTypeLike | None = mutagen.File(  # pyright: ignore[reportPrivateImportUsage, reportUnknownMemberType, reportAssignmentType]
            path
        )
        if file is None:
            return None
        tag_type = TagType.OTHER

    if file is not None:
        if codec is None:
            codec = _get_codec(file)
        return (file, codec, tag_type)
    else:
        return None


def _get_tags(file: MutagenFileTypeLike, tag_type: TagType):
    def store_value(key: str, value: Any):
        if hasattr(value, "text") and isinstance(value.text, list) and len(value.text):  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            return [str(text) for text in value.text]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType, reportUnknownMemberType]
        if hasattr(value, "pprint"):
            return str(value.pprint())
        if isinstance(value, list):
            return [textwrap.shorten(str(v), width=4096) for v in values]
        return textwrap.shorten(str(value), width=4096)

    tags: dict[str, list[str]] = {}
    if file.tags:
        for tag_name, tag_value in file.tags.items():
            name = str.lower(tag_name)
            if name.startswith("apic") or name == "covr":
                continue
            for value in tag_value if isinstance(tag_value, list) else [tag_value]:  # pyright: ignore[reportUnknownVariableType]
                values: str | list[str] = store_value(name, value)
                if isinstance(values, list):
                    tags.setdefault(name, []).extend(values)
                else:
                    tags.setdefault(name, []).append(values)

    if tag_type == TagType.ID3_FRAMES:
        if "trck" in tags:
            tracknumber_value = tags["trck"][0]
            if str.count(tracknumber_value, "/") == 1:
                [tracknumber, tracktotal] = tracknumber_value.split("/")
                tags["tracknumber"] = [tracknumber]
                tags["tracktotal"] = [tracktotal]
            else:
                tags["tracknumber"] = [tracknumber_value]
            del tags["trck"]

        if "tpos" in tags:
            discnumber_value = tags["tpos"][0]
            if str.count(discnumber_value, "/") == 1:
                [discnumber, disctotal] = discnumber_value.split("/")
                tags["discnumber"] = [discnumber]
                tags["disctotal"] = [disctotal]
            elif discnumber_value:
                tags["discnumber"] = [discnumber_value]
            del tags["tpos"]

        for common_tag, id3_tag in BASIC_TO_ID3.items():
            if id3_tag in tags:
                tags[common_tag] = tags[id3_tag]
                del tags[id3_tag]

    return tags


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


def _get_pictures(file: MutagenFileTypeLike, cache: PictureCache) -> Generator[Tuple[Picture, bytes], None, None]:
    if isinstance(file, FLAC):
        yield from _get_flac_pictures(file.pictures, cache)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
    elif isinstance(file, MP3) and file.tags:
        yield from get_id3_pictures(file.tags, cache)
    elif isinstance(file, OggVorbis):
        yield from _get_ogg_vorbis_pictures(file, cache)


def _get_flac_pictures(flac_pictures: list[FlacPicture], cache: PictureCache) -> Generator[Tuple[Picture, bytes], None, None]:
    for embed_ix, picture in enumerate(flac_pictures):
        image_data: bytes = picture.data  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        yield (_flac_picture_to_picture(embed_ix, picture, cache), image_data)


def get_picture_metadata(image_data: bytes, picture_type: PictureType, metadata_cache: PictureCache):
    file_size = len(image_data)
    xhash = xxhash.xxh32_digest(image_data)
    key = (file_size, xhash)
    if key in metadata_cache:
        pic = copy(metadata_cache[key])
        pic.picture_type = picture_type
        return pic

    image_info = get_image(image_data)
    if isinstance(image_info, str):
        pic = Picture(picture_type, "Unknown", 0, 0, file_size, xhash, "", {"error": image_info})
    else:
        (image, mimetype) = image_info
        pic = Picture(picture_type, mimetype, image.width, image.height, file_size, xhash)

    metadata_cache[key] = pic
    return pic


def _flac_picture_to_picture(embed_ix: int, flac_picture: FlacPicture, cache: PictureCache):
    picture_type = PictureType(flac_picture.type)
    image_data: bytes = flac_picture.data  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    picture = get_picture_metadata(image_data, picture_type, cache)  # pyright: ignore[reportUnknownArgumentType]
    picture.embed_ix = embed_ix

    load_error = picture.load_issue.get("error") if picture.load_issue else None
    if not load_error:
        # use "real" metadata from the image data but record if data in flac metadata block disagrees
        metadata_block_mimetype = str(flac_picture.mime) if isinstance(flac_picture.mime, str) else "Unknown"  # type: ignore
        mismatch = {}
        if picture.format != metadata_block_mimetype:
            mismatch["format"] = metadata_block_mimetype
        if picture.width != flac_picture.width or picture.height != flac_picture.height:
            mismatch["width"] = flac_picture.width
            mismatch["height"] = flac_picture.height
        if mismatch:
            picture.load_issue = mismatch
    return picture


def get_id3_pictures(tags: ID3, cache: PictureCache) -> Generator[Tuple[Picture, bytes], None, None]:
    picture_frames: list[APIC] = tags.getall("APIC")  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    for embed_ix, frame in enumerate(picture_frames):  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
        image_data: bytes = frame.data  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType, reportAttributeAccessIssue]
        picture_type = PictureType(frame.type)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        picture = get_picture_metadata(image_data, picture_type, cache)  # pyright: ignore[reportUnknownArgumentType]
        picture.embed_ix = embed_ix
        picture.description = frame.desc  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        load_error = picture.load_issue.get("error") if picture.load_issue else None
        if not load_error:
            # use "real" metadata from the image data but record if data in flac metadata block disagrees
            apic_mimetype = str(frame.mime) if isinstance(frame.mime, str) else "Unknown"  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            if picture.format != apic_mimetype:
                picture.load_issue = {"format": apic_mimetype}

        yield (picture, image_data)


def _get_ogg_vorbis_pictures(file: OggVorbis, cache: PictureCache) -> Generator[Tuple[Picture, bytes], None, None]:
    for embed_ix, flac_picture in enumerate(_get_metadata_picture_blocks_from_ogg_vorbis(file)):
        image_data: bytes = flac_picture.data  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        yield (_flac_picture_to_picture(embed_ix, flac_picture, cache), image_data)


def _get_metadata_picture_blocks_from_ogg_vorbis(file: OggVorbis) -> Generator[FlacPicture, None, None]:
    b64_pictures: list[str] = file.get("metadata_block_picture", [])  # pyright: ignore[reportUnknownVariableType, reportAssignmentType, reportUnknownMemberType]
    # TODO improve error handling here
    for b64_data in b64_pictures:
        metadata_block_raw = base64.b64decode(b64_data)
        yield FlacPicture(metadata_block_raw)


def remove_embedded_image(path: Path, codec: str, pic: Picture):
    if codec == "FLAC":
        return _remove_embedded_image_flac(path, pic)
    if codec == "MP3":
        return _remove_embedded_image_mp3(path, pic)
    if codec == "Ogg Vorbis":
        return _remove_embedded_image_ogg_vorbis(path, pic)
    logger.warning(f"cannot remove embedded image from {path.name} because file type not yet supported: {codec}")
    return False


def _remove_embedded_image_flac(path: Path, remove_pic: Picture):
    flac = FLAC(path)
    flac_pictures: list[FlacPicture] = flac.pictures  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    (match_ix, error) = _get_flac_picture_index(flac_pictures, remove_pic)
    if match_ix is None:
        logger.warning(f"could not remove {remove_pic.picture_type.name} picture from {path.name}: {error}")
        return False
    del flac_pictures[match_ix]
    flac.clear_pictures()
    for flac_picture in flac_pictures:
        flac.add_picture(flac_picture)  # pyright: ignore[reportUnknownMemberType]
    flac.save()  # pyright: ignore[reportUnknownMemberType]
    return True


def _remove_embedded_image_ogg_vorbis(path: Path, remove_pic: Picture):
    oggvorbis = OggVorbis(path)
    if not oggvorbis.tags:
        logger.warning(f"could not remove {remove_pic.picture_type.name} picture from {path.name}: no vorbis comments found")
        return False
    flac_pictures = list(_get_metadata_picture_blocks_from_ogg_vorbis(oggvorbis))
    (match_ix, error) = _get_flac_picture_index(flac_pictures, remove_pic)
    if match_ix is None:
        logger.warning(f"could not remove {remove_pic.picture_type.name} picture from {path.name}: {error}")
        return False
    del flac_pictures[match_ix]
    new_pictures = [flac_picture_to_vorbis_comment_value(pic) for pic in flac_pictures]
    oggvorbis.tags["metadata_block_picture"] = new_pictures
    oggvorbis.save()  # pyright: ignore[reportUnknownMemberType]
    return True


def _get_flac_picture_index(flac_pictures: Sequence[FlacPicture], match: Picture) -> tuple[int | None, str | None]:
    match_ix: int | None = None
    for ix, flac_picture in enumerate(flac_pictures):
        if ix == match.embed_ix:
            if match == _flac_picture_to_picture(ix, flac_picture, {}):
                match_ix = ix
                break
            else:
                return (None, f"wrong picture at index {ix} (scan again)")
    if match_ix is None:
        return (None, f"no picture at index {match.embed_ix} (scan again)")
    return (match_ix, None)


def _remove_embedded_image_mp3(path: Path, remove_pic: Picture):
    mp3 = MP3(path)
    if not mp3.tags:  # pyright: ignore[reportUnknownMemberType]
        logger.warning(f"could not remove {remove_pic.picture_type.name} picture from {path.name}: no ID3 tag")
        return False
    id3: ID3 = mp3.tags  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    pictures = list(get_id3_pictures(id3, {}))  # pyright: ignore[reportUnknownArgumentType]
    (match_ix, error) = _get_id3_picture_index(pictures, remove_pic)
    if match_ix is None:
        logger.warning(f"could not remove {remove_pic.picture_type.name} picture from {path.name}: {error}")
        return False
    del pictures[match_ix]
    id3.delall("APIC")  # pyright: ignore[reportUnknownMemberType]
    add_id3_pictures(id3, pictures)  # pyright: ignore[reportUnknownArgumentType]
    mp3.save()  # pyright: ignore[reportUnknownMemberType]
    return True


def _get_id3_picture_index(pictures: Sequence[Tuple[Picture, bytes]], match: Picture) -> tuple[int | None, str | None]:
    match_ix: int | None = None
    for ix, pic_info in enumerate(pictures):
        (pic, _) = pic_info
        if ix == match.embed_ix:
            if match == pic:
                match_ix = ix
                break
            else:
                return (None, f"wrong picture at index {ix} (scan again)")
    if match_ix is None:
        return (None, f"no picture at index {match.embed_ix} (scan again)")
    return (match_ix, None)


def add_id3_pictures(tags: ID3, pictures: Iterable[Tuple[Picture, bytes]]):
    for picture_info in pictures:
        (picture, image_data) = picture_info
        description = picture.description
        apic = APIC(mime=picture.format, type=picture.picture_type, data=image_data, desc=description)

        # with future mutagen 1.48 or later, docs indicate we will be able to ensure distinct hash key like this:
        # while apic.HashKey in tags:
        #     apic.salt += "x"  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        while apic.HashKey in tags:  # TODO don't alter description
            description += " "
            apic = APIC(mime=picture.format, type=picture.picture_type, data=image_data, desc=description)

        tags.add(apic)  # pyright: ignore[reportUnknownMemberType]


def flac_picture_to_vorbis_comment_value(flac_picture: FlacPicture) -> str:
    return base64.b64encode(flac_picture.write()).decode("ascii")


def get_image(image_data: bytes) -> tuple[Image.Image, str] | str:
    try:
        image = Image.open(io.BytesIO(image_data))
        image.load()
        mimetype: str | None = None
        if image.format:
            mimetype, _ = mimetypes.guess_type(f"_.{image.format}")
        if not mimetype:
            # we don't use container-specified MIME type except to note if it is wrong
            return f"couldn't guess MIME type for image format {image.format}"
        return (image, mimetype)
    except (IOError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as ex:
        exception_description = repr(ex)
        return "cannot identify image file" if "cannot identify image file" in exception_description else exception_description


def read_image(path: Path, embedded: bool, embed_ix: int) -> Tuple[Image.Image, bytes] | None:
    if embedded:
        images = get_embedded_image_data(path)
        image_data = images[embed_ix]
    else:
        with open(path, "rb") as f:
            image_data = f.read()
    try:
        image = Image.open(io.BytesIO(image_data))
    except UnidentifiedImageError as ex:
        logger.error(f"failed to read image {str(path)}: {repr(ex)}")
        image = None
    return (image, image_data) if image else None


IMAGE_MODE_BPP = {"RGB": 24, "RGBA": 32, "CMYK": 32, "YCbCr": 24, "I;16": 16, "I;16B": 16, "I;16L": 16, "I": 32, "F": 32, "1": 1}
