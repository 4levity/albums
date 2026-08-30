"""Fallback TaggerFile for any file mutagen can open, with Vorbis-like tag handling."""

import logging
from pathlib import Path
from typing import Callable, Final, Generator, List, Tuple, override

import mutagen
from mutagen._tags import PaddingInfo

from ..base_mutagen import AbstractMutagenTagger
from ..types import BasicField, MutagenFileType, Picture
from ..vorbis import vorbis_comment_fields, vorbis_comment_legacy_fields, vorbis_comment_set_field

logger: Final = logging.getLogger(__name__)


class UniversalTagger(AbstractMutagenTagger[MutagenFileType]):
    """Fallback tagger for unhandled file types that mutagen can open, treating tags Vorbis-comment-like."""

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
    def get_fields(self):
        try:
            return vorbis_comment_fields(self._file)  # pyright: ignore[reportArgumentType]
        except Exception as ex:
            logger.warning(f"error reading tags from {self._file.filename}: {repr(ex)}")
            return ()

    @override
    def get_legacy_fields(self):
        try:
            return vorbis_comment_legacy_fields(self._file.tags)  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
        except Exception as ex:
            logger.warning(f"error reading legacy fields from {self._file.filename}: {repr(ex)}")
            return ()

    @override
    def _set_field(self, field: BasicField | str, value: str | List[str] | None):
        try:
            vorbis_comment_set_field(self._file, field, value)  # pyright: ignore[reportArgumentType]
        except Exception as ex:
            logger.warning(f"error setting {field} in {self._file.filename}: {repr(ex)}")
