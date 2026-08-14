"""Tagger package for reading and writing audio file metadata."""

from .folder import AUDIO_FILE_SUFFIXES, AlbumTagger, Cap
from .provider import AlbumTaggerProvider
from .types import (
    BASIC_FIELDS,
    BasicField,
    ID3v1Policy,
    Picture,
    PictureType,
    StreamInfo,
    TaggerFile,
)
from .vorbis import LEGACY_VORBIS_FIELDS

__all__ = [
    "AlbumTagger",
    "AlbumTaggerProvider",
    "AUDIO_FILE_SUFFIXES",
    "BASIC_FIELDS",
    "BasicField",
    "Cap",
    "ID3v1Policy",
    "LEGACY_VORBIS_FIELDS",
    "Picture",
    "PictureType",
    "StreamInfo",
    "TaggerFile",
]
