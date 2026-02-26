import logging
from pathlib import Path
from typing import Callable, Generator, List, Tuple, override

import mutagen
from mutagen._tags import PaddingInfo

from .base_mutagen import AbstractMutagenTagger
from .helpers import vorbis_comment_set_tag, vorbis_comment_tags
from .types import AlbumPicture, BasicTag, MutagenFileType, PictureType

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
    def set_tag(self, tag: BasicTag, value: str | List[str] | None):
        try:
            vorbis_comment_set_tag(self._file, tag, value)  # pyright: ignore[reportArgumentType]
        except Exception as ex:
            logger.warning(f"error setting {tag} in {self._file.filename}: {repr(ex)}")

    @override
    def get_pictures(self) -> Generator[Tuple[AlbumPicture, bytes], None, None]:
        yield from ()

    @override
    def get_image_data(self, picture_type: PictureType, embed_ix: int) -> bytes:
        raise NotImplementedError(f"unsupported file: cannot read image#{embed_ix} type {picture_type} from {self._file.filename}")

    @override
    def _scan_tags(self):
        try:
            return vorbis_comment_tags(self._file)  # pyright: ignore[reportArgumentType]
        except Exception as ex:
            logger.warning(f"error reading tags from {self._file.filename}: {repr(ex)}")
            return ()

    @override
    def _get_file(self):
        return self._file
