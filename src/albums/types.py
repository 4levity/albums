from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union, overload

from rich.console import RenderableType
from sqlalchemy import REAL, Boolean, ForeignKey, Index, Integer, LargeBinary, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, composite, mapped_column, relationship

from .database.orm import NO_DEFAULT_VALUE_LIST_STR, Base, IntEnumAsInt, LoadIssuesAsJson, LoadIssuesType
from .picture.info import PictureInfo
from .tagger.types import BasicTag, Picture, PictureType, StreamInfo

type CheckConfiguration = Dict[str, Union[str, int, float, bool, Sequence[str]]]


class FixResult(Enum):
    NO_CHANGE = auto()
    CHANGED_ALBUM = auto()
    DELETED_ALBUM = auto()
    CHANGED_OTHER = auto()

    @staticmethod
    def of(changed: bool):
        return FixResult.CHANGED_ALBUM if changed else FixResult.NO_CHANGE


@dataclass
class Fixer:
    fix: Callable[[str], FixResult]
    options: Sequence[str]  # at least one option should be provided if "free text" is not an option
    option_free_text: bool = False
    option_automatic_index: int | None = None
    table: Tuple[Sequence[str], Sequence[Sequence[RenderableType]] | Callable[[], Sequence[Sequence[RenderableType]]]] | None = None
    prompt: str = "select an option"  # e.g. "select an album artist for all tracks"

    def get_table(self) -> Tuple[Sequence[str], Sequence[Sequence[RenderableType]]] | None:
        if self.table is None:
            return None
        (headers, get_rows) = self.table
        rows: Sequence[Sequence[RenderableType]] = get_rows if isinstance(get_rows, Sequence) else get_rows()  # pyright: ignore[reportUnknownVariableType]
        return (headers, rows)


@dataclass(frozen=True)
class CheckResult:
    message: str
    fixer: Fixer | None = None


class CollectionEntity(Base):
    __tablename__ = "collection"

    collection_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    collection_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"CollectionEntity({self.collection_name})"


class IgnoreCheckEntity(Base):
    __tablename__ = "album_ignore_check"
    __table_args__ = (Index("idx_ignore_check_album_id", "album_id"),)

    album_ignore_check_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("album.album_id"), nullable=False)
    album: Mapped[Optional[Album]] = relationship("Album", back_populates="ignore_check_entities")

    check_name: Mapped[str] = mapped_column(Text, nullable=False)

    def __init__(self, check_name: str):
        self.check_name = check_name


class TrackPicture(Base):
    __tablename__ = "track_picture"
    __table_args__ = (Index("idx_track_picture_track_id", "track_id"),)

    track_picture_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("track.track_id"), nullable=False)
    track: Mapped[Optional[Track]] = relationship("Track", back_populates="pictures")

    picture_type: Mapped[PictureType] = mapped_column(IntEnumAsInt[PictureType](PictureType), nullable=False)
    embed_ix: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    _format: Mapped[str] = mapped_column("format", Text, nullable=False)
    _width: Mapped[int] = mapped_column("width", Integer, nullable=False)
    _height: Mapped[int] = mapped_column("height", Integer, nullable=False)
    _depth_bpp: Mapped[int] = mapped_column("depth_bpp", Integer, nullable=False)
    _file_size: Mapped[int] = mapped_column("file_size", Integer, nullable=False)
    _file_hash: Mapped[bytes] = mapped_column("file_hash", LargeBinary, nullable=False)
    _load_issue: Mapped[LoadIssuesType] = mapped_column("load_issue", LoadIssuesAsJson)
    picture_info = composite(PictureInfo, _format, _width, _height, _depth_bpp, _file_size, _file_hash, _load_issue)

    def to_dict(self) -> dict[str, Any]:
        return {"picture_type": PictureType(self.picture_type), "description": self.description, "picture_info": self.picture_info.to_dict()}

    def to_picture(self) -> Picture:
        return Picture(self.picture_info, self.picture_type, self.description or "")

    def __lt__(self, other: TrackPicture):
        return self.embed_ix < other.embed_ix


class TagV(Base):
    __tablename__ = "track_tag"
    __table_args__ = (Index("idx_track_tag_track_id", "track_id"),)

    track_tag_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("track.track_id"), nullable=False)
    track: Mapped[Optional[Track]] = relationship("Track", back_populates="tags")

    tag: Mapped[BasicTag] = mapped_column("name", SqlEnum(BasicTag, native_enum=False, values_callable=lambda e: [x.value for x in e]))  # pyright: ignore[reportUnknownVariableType, reportUnknownLambdaType, reportUnknownMemberType]
    value: Mapped[str] = mapped_column(Text, nullable=False)


class Track(Base):
    __tablename__ = "track"
    __table_args__ = (Index("idx_track_album_id", "album_id"),)

    track_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("album.album_id"), nullable=False)
    album: Mapped[Optional[Album]] = relationship("Album", back_populates="tracks")

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    modify_timestamp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    _stream_length: Mapped[float] = mapped_column("stream_length", REAL, nullable=False, default=0)
    _stream_bitrate: Mapped[int] = mapped_column("stream_bitrate", Integer, nullable=False, default=0)
    _stream_channels: Mapped[int] = mapped_column("stream_channels", Integer, nullable=False, default=0)
    _stream_codec: Mapped[str] = mapped_column("stream_codec", Text, nullable=False, default="")
    _stream_sample_rate: Mapped[int] = mapped_column("stream_sample_rate", Integer, nullable=False, default=0)
    _stream_error: Mapped[str] = mapped_column("stream_error", Text, nullable=False, default="")
    stream = composite(StreamInfo, _stream_length, _stream_bitrate, _stream_channels, _stream_codec, _stream_sample_rate, _stream_error)

    pictures: Mapped[List[TrackPicture]] = relationship("TrackPicture", back_populates="track", cascade="all, delete-orphan")
    tags: Mapped[List[TagV]] = relationship("TagV", back_populates="track", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "file_size": self.file_size,
            "modify_timestamp": self.modify_timestamp,
            "pictures": [picture.to_dict() for picture in sorted(self.pictures, key=lambda pic: pic.embed_ix)],
            "stream": self.stream.to_dict() if self.stream else {},
            "tags": self.tag_dict(),
        }

    def tag_dict(self) -> Mapping[BasicTag, Sequence[str]]:
        tags: dict[BasicTag, List[str]] = {}
        for tag_entity in self.tags:
            tags.setdefault(tag_entity.tag, []).append(tag_entity.value)
        return tags

    def has(self, tag: BasicTag) -> bool:
        return any(t.tag == tag for t in self.tags)

    @overload
    def get(self, tag: BasicTag, default: None) -> Sequence[str] | None: ...
    @overload
    def get(self, tag: BasicTag, default: Sequence[str] = NO_DEFAULT_VALUE_LIST_STR) -> Sequence[str]: ...
    def get(self, tag: BasicTag, default: Sequence[str] | None = NO_DEFAULT_VALUE_LIST_STR) -> Sequence[str] | None:
        result = tuple(t.value for t in self.tags if t.tag == tag)
        if len(result) == 0:
            if default is NO_DEFAULT_VALUE_LIST_STR:
                raise KeyError(f"{tag.value} is not in tags")
            return default
        return result

    def __init__(self, **kw: Any):
        if "tags" not in kw and "tag" in kw and isinstance(kw["tag"], Mapping):
            t: Mapping[BasicTag, str | Sequence[str]] = kw["tag"]  # pyright: ignore[reportUnknownVariableType]
            kw["tags"] = [TagV(tag=tag, value=v) for tag, values in t.items() for v in ([values] if isinstance(values, str) else values)]
            del kw["tag"]
        super().__init__(**kw)

    def __lt__(self, other: Track | PictureFile | OtherFile):
        return self.filename < other.filename


class PictureFile(Base):
    __tablename__ = "album_picture_file"
    __table_args__ = (Index("idx_album_picture_file_album_id", "album_id"),)

    album_picture_file_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("album.album_id"), nullable=False)
    album: Mapped[Optional[Album]] = relationship("Album", back_populates="picture_files")

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column("file_size", Integer, nullable=False, default=0)
    modify_timestamp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cover_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    _format: Mapped[str] = mapped_column("format", Text, nullable=False, default="")
    _width: Mapped[int] = mapped_column("width", Integer, nullable=False, default=0)
    _height: Mapped[int] = mapped_column("height", Integer, nullable=False, default=0)
    _depth_bpp: Mapped[int] = mapped_column("depth_bpp", Integer, nullable=False, default=0)
    _file_hash: Mapped[bytes] = mapped_column("file_hash", LargeBinary, nullable=False, default=b"")
    _load_issue: Mapped[LoadIssuesType] = mapped_column("load_issue", LoadIssuesAsJson)
    picture_info = composite(PictureInfo, _format, _width, _height, _depth_bpp, file_size, _file_hash, _load_issue)

    def to_dict(self):
        return {
            "filename": self.filename,
            "modify_timestamp": self.modify_timestamp,
            "cover_source": self.cover_source,
            "picture_info": self.picture_info.to_dict(),
        }

    def to_picture(self) -> Picture:
        return Picture(self.picture_info, PictureType.from_filename(self.filename), "")

    def __lt__(self, other: Track | PictureFile | OtherFile):
        return self.filename < other.filename


class OtherFile(Base):
    __tablename__ = "album_other_file"
    __table_args__ = (Index("idx_album_other_file_album_id", "album_id"),)

    album_other_file_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("album.album_id"), nullable=False)
    album: Mapped[Optional[Album]] = relationship("Album", back_populates="other_files")

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column("file_size", Integer, nullable=False, default=0)
    modify_timestamp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            "filename": self.filename,
            "modify_timestamp": self.modify_timestamp,
            "file_size": self.file_size,
        }

    def __lt__(self, other: Track | PictureFile | OtherFile):
        return self.filename < other.filename


class Album(Base):
    __tablename__ = "album"
    __table_args__ = (Index("album_path", "path", unique=True),)

    album_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)

    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    scanner: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    collection_associations: Mapped[List[AlbumCollectionAssociation]] = relationship(back_populates="album", cascade="all, delete-orphan")
    collections: AssociationProxy[List[str]] = association_proxy(
        "collection_associations",
        "collection_name",
        creator=lambda collection_name: AlbumCollectionAssociation(collection=CollectionEntity(collection_name=collection_name)),  # pyright: ignore
    )
    ignore_check_entities: Mapped[List[IgnoreCheckEntity]] = relationship("IgnoreCheckEntity", back_populates="album", cascade="all, delete-orphan")
    ignore_checks: AssociationProxy[List[str]] = association_proxy("ignore_check_entities", "check_name")
    other_files: Mapped[List[OtherFile]] = relationship("OtherFile", back_populates="album", cascade="all, delete-orphan")
    picture_files: Mapped[List[PictureFile]] = relationship("PictureFile", back_populates="album", cascade="all, delete-orphan")
    tracks: Mapped[List[Track]] = relationship("Track", back_populates="album", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        return {
            "album_id": self.album_id,
            "path": self.path,
            "scanner": self.scanner,
            "collections": list(self.collections),
            "ignore_checks": list(self.ignore_checks),
            "tracks": [track.to_dict() for track in self.tracks],
            "picture_files": [picture_file.to_dict() for picture_file in self.picture_files],
            "other_files": [other_file.to_dict() for other_file in self.other_files],
        }


class AlbumCollectionAssociation(Base):
    __tablename__ = "album_collection"

    album_collection_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[int] = mapped_column(Integer, ForeignKey("album.album_id"))
    collection_id: Mapped[int] = mapped_column(Integer, ForeignKey("collection.collection_id"))

    collection: Mapped[CollectionEntity] = relationship()
    collection_name: AssociationProxy[str] = association_proxy("collection", "collection_name")

    album: Mapped[Album] = relationship(back_populates="collection_associations")


class ScanHistoryEntity(Base):
    __tablename__ = "scan_history"
    __table_args__ = (Index("idx_scan_history_timestamp", "timestamp"),)

    scan_history_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)

    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    folders_scanned: Mapped[int] = mapped_column(Integer, nullable=False)
    albums_total: Mapped[int] = mapped_column(Integer, nullable=False)
