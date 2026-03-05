import logging
from pathlib import Path
from typing import Callable, Generator, List, Tuple, override

import mutagen
from mutagen._tags import PaddingInfo

from .base_mutagen import AbstractMutagenTagger
from .helpers import vorbis_comment_set_tag, vorbis_comment_tags
from .types import BasicTag, MutagenFileType, Picture

logger = logging.getLogger(__name__)


class UniversalTagger(AbstractMutagenTagger):
    _file: MutagenFileType

    def __init__(self, path: Path, padding: Callable[[PaddingInfo], int]):
        super().__init__(padding)
        file = mutagen.File(path)  # pyright: ignore[reportAssignmentType, reportUnknownMemberType, reportPrivateImportUsage]
        if file is None:
            raise ValueError(f"can't open file {str(path)}")
        self._file = file

    @override
    def _get_file(self):
        return self._file

    @override
    def get_pictures(self) -> Generator[Tuple[Picture, bytes], None, None]:
        yield from ()

    @override
    def _add_picture(self, new_picture: Picture, image_data: bytes) -> None:
        raise NotImplementedError(f"unsupported file: cannot add {new_picture.type.name} picture to {self._file.filename}")

    @override
    def _remove_picture(self, remove_picture: Picture) -> None:
        raise NotImplementedError(f"unsupported file: cannot remove {remove_picture.type.name} picture from {self._file.filename}")

    @override
    def _scan_tags(self):
        try:
            return vorbis_comment_tags(self._file)  # pyright: ignore[reportArgumentType]
        except Exception as ex:
            logger.warning(f"error reading tags from {self._file.filename}: {repr(ex)}")
            return ()

    @override
    def _set_tag(self, tag: BasicTag, value: str | List[str] | None):
        try:
            vorbis_comment_set_tag(self._file, tag, value)  # pyright: ignore[reportArgumentType]
        except Exception as ex:
            logger.warning(f"error setting {tag} in {self._file.filename}: {repr(ex)}")
