from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence, Unpack

from sqlalchemy import REAL, Boolean, Column, Enum, ForeignKey, Index, Integer, LargeBinary, Table, Text, text
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import DeclarativeBase, Mapped, composite, mapped_column, relationship

from ..configuration import SettingValueType
from ..picture.info import PictureInfo
from ..tagger.types import BasicTag, PictureType, StreamInfo
from .orm_helpers import GetDefaultOption, IntEnumAsInt, LoadIssuesAsJson, LoadIssuesType, SerializableValueAsJson


class Base(DeclarativeBase):
    pass


schema_table = Table("_schema", Base.metadata, Column("version", Integer, nullable=False, unique=True))


class AlbumCollectionAssociation(Base):
    __tablename__ = "album_collection"

    album_collection_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[int] = mapped_column(Integer, ForeignKey("album.album_id"))
    collection_id: Mapped[int] = mapped_column(Integer, ForeignKey("collection.collection_id"))

    collection: Mapped[CollectionEntity] = relationship()
    collection_name: AssociationProxy[str] = association_proxy("collection", "collection_name")

    album: Mapped[AlbumEntity] = relationship(back_populates="collection_associations")


class AlbumEntity(Base):
    __tablename__ = "album"
    __table_args__ = (Index("album_path", "path", unique=True),)

    album_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)

    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    scanner: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    collection_associations: Mapped[List[AlbumCollectionAssociation]] = relationship(back_populates="album", cascade="all, delete-orphan")
    collections: AssociationProxy[List[str]] = association_proxy(
        "collection_associations",
        "collection_name",
        creator=lambda collection_name: AlbumCollectionAssociation(collection=CollectionEntity(collection_name=collection_name)),  # pyright: ignore
    )
    ignore_check_entities: Mapped[List[IgnoreCheckEntity]] = relationship("IgnoreCheckEntity", back_populates="album")
    ignore_checks: AssociationProxy[List[str]] = association_proxy("ignore_check_entities", "check_name")
    picture_files: Mapped[List[PictureFileEntity]] = relationship("PictureFileEntity", back_populates="album")
    tracks: Mapped[List[TrackEntity]] = relationship("TrackEntity", back_populates="album")

    def to_dict(self) -> dict[str, Any]:
        return {
            "album_id": self.album_id,
            "path": self.path,
            "scanner": self.scanner,
            "collections": list(self.collections),
            "ignore_checks": list(self.ignore_checks),
            "tracks": [track.to_dict() for track in self.tracks],
            "picture_files": [picture_file.to_dict() for picture_file in self.picture_files],
        }


class CollectionEntity(Base):
    __tablename__ = "collection"

    collection_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    collection_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"CollectionEntity({self.collection_name})"


class ScanHistoryEntity(Base):
    __tablename__ = "scan_history"
    __table_args__ = (Index("idx_scan_history_timestamp", "timestamp"),)

    scan_history_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)

    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    folders_scanned: Mapped[int] = mapped_column(Integer, nullable=False)
    albums_total: Mapped[int] = mapped_column(Integer, nullable=False)


class SettingEntity(Base):
    __tablename__ = "setting"

    name: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    value: Mapped[SettingValueType] = mapped_column("value_json", SerializableValueAsJson[SettingValueType], nullable=False)


class IgnoreCheckEntity(Base):
    __tablename__ = "album_ignore_check"
    __table_args__ = (Index("idx_ignore_check_album_id", "album_id"),)

    album_ignore_check_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("album.album_id"), nullable=False)
    album: Mapped[Optional[AlbumEntity]] = relationship("AlbumEntity", back_populates="ignore_check_entities")

    check_name: Mapped[str] = mapped_column(Text, nullable=False)

    def __init__(self, check_name: str):
        self.check_name = check_name


class PictureFileEntity(Base):
    __tablename__ = "album_picture_file"
    __table_args__ = (Index("idx_album_picture_file_album_id", "album_id"),)

    album_picture_file_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("album.album_id"), nullable=False)
    album: Mapped[Optional[AlbumEntity]] = relationship("AlbumEntity", back_populates="picture_files")

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    modify_timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    cover_source: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))
    _format: Mapped[str] = mapped_column("format", Text, nullable=False)
    _width: Mapped[int] = mapped_column("width", Integer, nullable=False)
    _height: Mapped[int] = mapped_column("height", Integer, nullable=False)
    _depth_bpp: Mapped[int] = mapped_column("depth_bpp", Integer, nullable=False)
    _file_size: Mapped[int] = mapped_column("file_size", Integer, nullable=False)
    _file_hash: Mapped[bytes] = mapped_column("file_hash", LargeBinary, nullable=False)
    _load_issue: Mapped[LoadIssuesType] = mapped_column("load_issue", LoadIssuesAsJson)
    picture_info = composite(PictureInfo, _format, _width, _height, _depth_bpp, _file_size, _file_hash, _load_issue)

    def to_dict(self):
        return {
            "filename": self.filename,
            "modify_timestamp": self.modify_timestamp,
            "cover_source": self.cover_source,
            "picture_info": self.picture_info.to_dict(),
        }


class TrackEntity(Base):
    __tablename__ = "track"
    __table_args__ = (Index("idx_track_album_id", "album_id"),)

    track_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("album.album_id"), nullable=False)
    album: Mapped[Optional[AlbumEntity]] = relationship("AlbumEntity", back_populates="tracks")

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    modify_timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    _stream_length: Mapped[float] = mapped_column("stream_length", REAL, nullable=False)
    _stream_bitrate: Mapped[int] = mapped_column("stream_bitrate", Integer, nullable=False)
    _stream_channels: Mapped[int] = mapped_column("stream_channels", Integer, nullable=False)
    _stream_codec: Mapped[str] = mapped_column("stream_codec", Text, nullable=False)
    _stream_sample_rate: Mapped[int] = mapped_column("stream_sample_rate", Integer, nullable=False)
    stream = composite(StreamInfo, _stream_length, _stream_bitrate, _stream_channels, _stream_codec, _stream_sample_rate)

    pictures: Mapped[List[TrackPictureEntity]] = relationship("TrackPictureEntity", back_populates="track")
    tags: Mapped[List[TrackTagEntity]] = relationship("TrackTagEntity", back_populates="track")

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

    def get(self, tag: BasicTag, **kwargs: Unpack[GetDefaultOption[Sequence[str]]]) -> Sequence[str]:
        result = tuple(t.value for t in self.tags if t.tag == tag)
        if len(result) == 0:
            if "default" in kwargs:
                return kwargs["default"]
            raise KeyError(f"{tag.value} is not in tags")
        return result


class TrackPictureEntity(Base):
    __tablename__ = "track_picture"
    __table_args__ = (Index("idx_track_picture_track_id", "track_id"),)

    track_picture_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("track.track_id"), nullable=False)
    track: Mapped[Optional[TrackEntity]] = relationship("TrackEntity", back_populates="pictures")

    picture_type: Mapped[PictureType] = mapped_column(IntEnumAsInt[PictureType](PictureType), nullable=False)
    embed_ix: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
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


class TrackTagEntity(Base):
    __tablename__ = "track_tag"
    __table_args__ = (Index("idx_track_tag_track_id", "track_id"),)

    track_tag_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("track.track_id"), nullable=False)
    track: Mapped[Optional[TrackEntity]] = relationship("TrackEntity", back_populates="tags")

    tag: Mapped[BasicTag] = mapped_column("name", Enum(BasicTag, native_enum=False, values_callable=lambda e: [x.value for x in e]))  # pyright: ignore[reportUnknownVariableType, reportUnknownLambdaType, reportUnknownMemberType]
    value: Mapped[str] = mapped_column(Text, nullable=False)
