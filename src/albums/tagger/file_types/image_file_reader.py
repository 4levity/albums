from pathlib import Path
from typing import Generator, Sequence, Tuple, override

from ...picture.scan import PictureScanner
from ..types import BasicTag, Picture, PictureType, ScanResult, StreamInfo, TaggerFile


class ImageFileReader(TaggerFile):
    _path: Path
    _picture_scanner: PictureScanner
    _image: Tuple[Picture, bytes] | None = None

    def __init__(self, path: Path, picture_scanner: PictureScanner):
        self._path = path
        self._picture_scanner = picture_scanner

    @override
    def has_video(self) -> bool:
        return False

    @override
    def scan(self) -> ScanResult:
        return ScanResult((), tuple(pic for pic, _ in self.get_pictures()), StreamInfo())

    @override
    def get_image_data(self, picture: Picture) -> bytes:
        return next(data for _pic, data in self.get_pictures())

    @override
    def get_pictures(self) -> Generator[Tuple[Picture, bytes], None, None]:
        if not self._image:
            with open(self._path, "rb") as f:
                image_data = f.read()
            picture_info = self._picture_scanner.scan(image_data)
            picture = Picture(picture_info, PictureType.from_filename(self._path.name), "")
            self._image = (picture, image_data)
        yield self._image

    @override
    def set_tag(self, tag: BasicTag, value: str | Sequence[str] | None) -> None:
        raise NotImplementedError("ImageFileReader")

    @override
    def add_picture(self, new_picture: Picture, image_data: bytes) -> None:
        raise NotImplementedError("ImageFileReader")

    @override
    def remove_picture(self, remove_picture: Picture) -> None:
        raise NotImplementedError("ImageFileReader")

    @override
    def close(self) -> None:
        pass
