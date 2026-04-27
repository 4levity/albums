from typing import Generator, List, Tuple, override

from .types import BasicTag, Picture, StreamInfo, TaggerFile


class UnreadableTagger(TaggerFile):
    _filename: str
    _error: str

    def __init__(self, filename: str, error: str):
        self._filename = filename
        self._error = error

    @override
    def get_tags(self):
        return ()

    @override
    def get_stream_info(self):
        return StreamInfo(0, 0, 0, "unknown", 0, self._error)

    @override
    def get_image_data(self, picture: Picture) -> bytes:
        raise ValueError(f"cannot read images - unreadable file {self._filename}")

    @override
    def get_pictures(self) -> Generator[Tuple[Picture, bytes], None, None]:
        yield from ()

    @override
    def has_video(self) -> bool:
        return False

    @override
    def set_tag(self, tag: BasicTag, value: str | List[str] | None) -> None:
        raise ValueError(f"cannot set tags - unreadable file {self._filename}")

    @override
    def add_picture(self, new_picture: Picture, image_data: bytes) -> None:
        raise ValueError(f"cannot add picture - unreadable file {self._filename}")

    @override
    def remove_picture(self, remove_picture: Picture) -> None:
        raise ValueError(f"cannot add picture - unreadable file {self._filename}")

    @override
    def close(self) -> None:
        pass
