import logging
from typing import Any, Callable, List, Tuple, override

from mutagen._tags import PaddingInfo

from .types import BasicTag, MutagenFileType, Picture, ScanResult, StreamInfo, TaggerFile

ALL_BASIC_TAGS = frozenset(tag.value for tag in BasicTag)
MAX_BASIC_TAG_VALUE_LENGTH = 4096

logger = logging.getLogger(__name__)


class AbstractMutagenTagger[_FT: MutagenFileType](TaggerFile):
    _changed = False
    _padding: Callable[[PaddingInfo], int]

    def __init__(self, padding: Callable[[PaddingInfo], int]):
        self._padding = padding

    # subclass must implement
    def _get_file(self) -> _FT: ...
    def _scan_tags(self) -> Tuple[Tuple[BasicTag, Tuple[str, ...]], ...]: ...
    def _set_tag(self, tag: BasicTag, value: str | List[str] | None) -> None: ...
    def _add_picture(self, new_picture: Picture, image_data: bytes) -> None: ...
    def _remove_picture(self, remove_picture: Picture) -> None: ...

    # subclass MAY implement
    def _get_codec(self) -> str:
        file = self._get_file()
        codec = _find_codec(file.info)  # pyright: ignore[reportUnknownMemberType]
        if codec:
            return codec
        else:
            logger.warning(f"couldn't determine codec in {file.filename}")
            return "unknown"

    def _save(self):
        self._get_file().save(padding=self._padding)  # pyright: ignore[reportUnknownMemberType]

    @override
    def scan(self) -> ScanResult:
        file = self._get_file()
        stream_info = _get_stream_info(file.filename, file.info, self._get_codec())  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
        return ScanResult(self._scan_tags(), tuple(pic for pic, _data in self.get_pictures()), stream_info)

    @override
    def get_image_data(self, picture: Picture) -> bytes:
        pic_info = next(((pic, data) for pic, data in self.get_pictures() if pic == picture), None)
        if pic_info is None:
            raise ValueError(f"cannot find matching {picture.type.name} image in {self._get_file().filename}")
        (_, image_data) = pic_info
        return image_data

    def set_tag(self, tag: BasicTag, value: str | List[str] | None) -> None:
        self._set_tag(tag, value)
        self._changed = True

    def add_picture(self, new_picture: Picture, image_data: bytes) -> None:
        self._add_picture(new_picture, image_data)
        self._changed = True

    def remove_picture(self, remove_picture: Picture) -> None:
        self._remove_picture(remove_picture)
        self._changed = True

    @override
    def close(self):
        if self._changed:
            self._save()


def _get_stream_info(filename: str, mutagen_file_info: Any, codec: str) -> StreamInfo:
    # maybe this isn't necessary but I don't think there's a guarantee that these attributes exist
    if hasattr(mutagen_file_info, "length"):
        length = float(mutagen_file_info.length)
    else:
        length = 0.0
        logger.warning(f"couldn't determine stream length in {filename}")

    if hasattr(mutagen_file_info, "bitrate"):
        bitrate = int(mutagen_file_info.bitrate)
    else:
        bitrate = 0
        logger.warning(f"couldn't determine stream bitrate in {filename}")

    if hasattr(mutagen_file_info, "channels"):
        channels = int(mutagen_file_info.channels)
    else:
        channels = 0
        logger.warning(f"couldn't determine stream channels in {filename}")

    if hasattr(mutagen_file_info, "sample_rate"):
        sample_rate = int(mutagen_file_info.sample_rate)
    else:
        sample_rate = 0
        logger.warning(f"couldn't determine stream sample rate in {filename}")

    return StreamInfo(length, bitrate, channels, codec, sample_rate)


def _find_codec(mutagen_file_info: Any):
    if hasattr(mutagen_file_info, "codec_name"):
        return f"{mutagen_file_info.codec_name}"
    if hasattr(mutagen_file_info, "codec"):
        return f"{mutagen_file_info.codec}"
    if hasattr(mutagen_file_info, "pprint"):
        return mutagen_file_info.pprint().split(",")[0]
    return None
