"""Shared type definitions for library entities, check/fixer contracts, and result reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union, overload

from rich.console import RenderableType
from sqlalchemy import REAL, Boolean, ForeignKey, Index, Integer, LargeBinary, Text
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, composite, mapped_column, relationship

from .database.orm import NO_DEFAULT_VALUE_LIST_STR, Base, IntEnumAsInt, LoadIssuesAsJson, LoadIssuesType, SafeStringEnum
from .picture.info import PictureInfo
from .tagger.types import BasicTag, Picture, PictureType, StreamInfo

# Mapping type representing the configuration items available for a single registered check.
type CheckConfiguration = Dict[str, Union[str, int, float, bool, Sequence[str]]]


class FixResult(Enum):
    """Outcome codes returned by fixer callbacks to signal database mutation status."""

    NO_CHANGE = auto()  # The fix ran but did not alter any persisted data.
    CHANGED_ALBUM = auto()  # Album-level metadata was mutated; re-scan may be required.
    DELETED_ALBUM = auto()  # An entire album was deleted.
    CHANGED_OTHER = auto()  # Non-album resources (files, collections) were modified.

    @staticmethod
    def of(changed: bool) -> "FixResult":
        """Convenience factory mapping a boolean to either ``NO_CHANGE`` or ``CHANGED_ALBUM``.

        Args:
            changed: ``True`` when the fix mutated library state.

        Returns:
            ``CHANGED_ALBUM`` if *changed* else ``NO_CHANGE``.
        """
        return FixResult.CHANGED_ALBUM if changed else FixResult.NO_CHANGE


@dataclass
class Fixer:
    """Encapsulates a proposed correction along with user-interface hints for interactive mode.

    When a check detects a problem, it may attach a *Fixer* to the ``CheckResult`` so the system
    (or an interactive terminal prompt) can present options and apply the chosen fix.

    Attributes:
        fix: Callable accepting a selected option string and returning a ``FixResult``.
        options: Human-readable choices presented to the user; must have at least one entry when free text is disabled.
        option_free_text: When ``True``, offer the user an arbitrary text value in addition to *options*.
        option_automatic_index: Index into *options* representing the automatic choice or None if no automatic choice.
        table: Optional tabular data (headers + rows or row-factory callable) to display alongside options.
        prompt: Text displayed above the options when asking for user input.
    """

    fix: Callable[[str], FixResult]
    options: Sequence[str]
    option_free_text: bool = False
    option_automatic_index: int | None = None
    table: Tuple[Iterable[str], Iterable[Iterable[RenderableType]] | Callable[[], Iterable[Iterable[RenderableType]]]] | None = None
    prompt: str = "select an option"  # e.g. "select an album artist for all tracks"

    def get_table(self) -> Tuple[Iterable[str], Iterable[Iterable[RenderableType]]] | None:
        """Resolve the table hint into concrete headers and row data.

        If the stored rows were a lazy factory, they are invoked here so checks that defer expensive
        computation can remain fast unless an interactive prompt actually renders.

        Returns:
            A ``(headers, rows)`` tuple or ``None`` when no table was configured.
        """
        if self.table is None:
            return None
        (headers, get_rows) = self.table
        rows: Iterable[Iterable[RenderableType]] = get_rows if isinstance(get_rows, Iterable) else get_rows()  # pyright: ignore[reportUnknownVariableType]
        return (headers, rows)


@dataclass(frozen=True)
class CheckResult:
    """Outcome returned by check implementations to signal a problem that needs attention.

    Attributes:
        message: Human-readable description of what is wrong or missing for the album.
        fixer: Optional correction proposal; when ``None`` the user must handle the issue manually.
    """

    message: str
    fixer: Fixer | None = None


class CollectionEntity(Base):
    """Named group used to bucket albums so sync and filter commands can target a subset of the library.

    Attributes:
        collection_id: Primary key (auto-generated).
        collection_name: Unique display name for this collection.
    """

    __tablename__ = "collection"

    collection_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    collection_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"CollectionEntity({self.collection_name})"


class IgnoreCheckEntity(Base):
    """Row recording that one or more checks should be skipped for a specific album.

    Attributes:
        album_ignore_check_id: Primary key.
        album_id: Foreign key linking to the ``album`` row.
        album: ORM back-reference to the owning :class:`Album`.
        check_name: Name of the check to suppress (matches a registered check's *name*).
    """

    __tablename__ = "album_ignore_check"
    __table_args__ = (Index("idx_ignore_check_album_id", "album_id"),)

    album_ignore_check_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("album.album_id"), nullable=False)
    album: Mapped[Optional[Album]] = relationship("Album", back_populates="ignore_check_entities")

    check_name: Mapped[str] = mapped_column(Text, nullable=False)

    def __init__(self, check_name: str):
        self.check_name = check_name


class LegacyTagEntity(Base):
    """Stores legacy/deprecated tag field names used by a track, indicating why the tag should be updated.

    Attributes:
        track_legacy_tag_id: Primary key.
        track_id: Foreign key linking to the owning ``track`` row.
        track: ORM back-reference to the :class:`Track`.
        tag_name: Free-form raw tag label (as present in the original media file).
    """

    __tablename__ = "track_legacy_tag"
    __table_args__ = (Index("idx_legacy_tag_track_id", "track_id"),)

    track_legacy_tag_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("track.track_id"), nullable=False)
    track: Mapped[Optional[Track]] = relationship("Track", back_populates="legacy_tag_entities")

    tag_name: Mapped[str] = mapped_column(Text, nullable=False)

    def __init__(self, tag_name: str):
        self.tag_name = tag_name


class TrackPicture(Base):
    """Embedded artwork stored within a single audio track file.

    Attributes:
        track_picture_id: Primary key.
        track_id: Foreign key linking to the owning :class:`Track`.
        track: ORM back-reference to the parent track.
        picture_type: Image purpose (front cover, lyric text, etc.) per :class:`~.tagger.types.PictureType`.
        embed_ix: Numeric ordering when a track carries multiple embedded images.
        description: Human-readable caption for the artwork, if any.
        picture_info: Composite property exposing ``(format, width, height, depth_bpp, file_size, file_hash, load_issue)`` via :class:`~.picture.info.PictureInfo`.
    """

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
        """Serialize embedded picture data for JSON/CLI export."""
        return {"picture_type": PictureType(self.picture_type), "description": self.description, "picture_info": self.picture_info.to_dict()}

    def to_picture(self) -> Picture:
        """Convert this DB row into a plain ``Picture`` value object for tagger consumption."""
        return Picture(self.picture_info, self.picture_type, self.description or "")

    def __lt__(self, other: TrackPicture) -> bool:
        return self.embed_ix < other.embed_ix


class TagV(Base):
    """Single metadata tag value belonging to a track.

    When multiple frames share the same tag name (e.g., duplicate ``TCON`` genres), each gets its own row.

    Attributes:
        track_tag_id: Primary key.
        track_id: Foreign key linking to the owning :class:`Track`.
        track: ORM back-reference to the parent track.
        tag: Canonicalized tag name from :class:`~.tagger.types.BasicTag`.
        value: Decoded text content of this single metadata frame.
    """

    __tablename__ = "track_tag"
    __table_args__ = (Index("idx_track_tag_track_id", "track_id"),)

    track_tag_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("track.track_id"), nullable=False)
    track: Mapped[Optional[Track]] = relationship("Track", back_populates="tags")

    tag: Mapped[BasicTag] = mapped_column("name", SafeStringEnum[BasicTag](BasicTag, BasicTag.UNKNOWN), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class Track(Base):
    """Represents one audio file and its embedded metadata.

    Attributes:
        track_id: Primary key (auto-generated).
        album_id: Foreign key linking to the parent :class:`Album` row.
        album: ORM back-reference to the owning album.
        filename: Basename of the audio file as scanned from disk.
        file_size: Size on disk in bytes.
        modify_timestamp: UNIX epoch when this file was last written.
        stream: Composite property wrapping :class:`~.tagger.types.StreamInfo` with codec and duration details.
        pictures: Collection of embedded :class:`TrackPicture` objects.
        tags: Collection of decoded metadata as :class:`TagV` rows.
        legacy_tags: Association proxy mapping to non-standard :class:`LegacyTagEntity` field names.
    """

    __tablename__ = "track"
    __table_args__ = (Index("idx_track_album_id", "album_id"),)

    track_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("album.album_id"), nullable=False)
    album: Mapped[Optional[Album]] = relationship("Album", back_populates="tracks")

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    modify_timestamp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stream_length: Mapped[float] = mapped_column("stream_length", REAL, nullable=False, default=0)
    stream_bitrate: Mapped[int] = mapped_column("stream_bitrate", Integer, nullable=False, default=0)
    stream_channels: Mapped[int] = mapped_column("stream_channels", Integer, nullable=False, default=0)
    stream_codec: Mapped[str] = mapped_column("stream_codec", Text, nullable=False, default="")
    stream_sample_rate: Mapped[int] = mapped_column("stream_sample_rate", Integer, nullable=False, default=0)
    stream_bits_per_sample: Mapped[int] = mapped_column("stream_bits_per_sample", Integer, nullable=False, default=0)
    stream_error: Mapped[str] = mapped_column("stream_error", Text, nullable=False, default="")
    stream = composite(
        StreamInfo, stream_length, stream_bitrate, stream_channels, stream_codec, stream_sample_rate, stream_bits_per_sample, stream_error
    )

    pictures: Mapped[List[TrackPicture]] = relationship("TrackPicture", back_populates="track", cascade="all, delete-orphan")
    tags: Mapped[List[TagV]] = relationship("TagV", back_populates="track", cascade="all, delete-orphan")
    legacy_tag_entities: Mapped[List[LegacyTagEntity]] = relationship("LegacyTagEntity", back_populates="track", cascade="all, delete-orphan")
    legacy_tags: AssociationProxy[List[str]] = association_proxy("legacy_tag_entities", "tag_name")

    def to_dict(self) -> dict[str, Any]:
        """Serialize track and embedded metadata for JSON/CLI export."""
        return {
            "filename": self.filename,
            "file_size": self.file_size,
            "modify_timestamp": self.modify_timestamp,
            "pictures": [picture.to_dict() for picture in sorted(self.pictures, key=lambda pic: pic.embed_ix)],
            "stream": self.stream.to_dict() if self.stream else {},
            "tags": self.tag_dict(),
        }

    def tag_dict(self) -> Mapping[BasicTag, List[str]]:
        """Return all stored tags grouped by :class:`~.tagger.types.BasicTag` key.

        Returns:
            Mapping where each value is a list of frame text for that tag name.
        """
        tags: dict[BasicTag, List[str]] = {}
        for tag_entity in self.tags:
            tags.setdefault(tag_entity.tag, []).append(tag_entity.value)
        return tags

    def has(self, tag: BasicTag) -> bool:
        """Return ``True`` when at least one value for *tag* exists.

        Args:
            tag: The :class:`~.tagger.types.BasicTag` to check for.
        """
        return any(t.tag == tag for t in self.tags)

    @overload
    def get(self, tag: BasicTag, default: None) -> Sequence[str] | None: ...
    @overload
    def get(self, tag: BasicTag, default: Sequence[str] = NO_DEFAULT_VALUE_LIST_STR) -> Sequence[str]: ...
    def get(self, tag: BasicTag, default: Sequence[str] | None = NO_DEFAULT_VALUE_LIST_STR) -> Sequence[str] | None:
        """Retrieve all values for *tag*, optionally with a default if no values available.

        If no default is specified and no values exist, raises ``KeyError``.

        Args:
            tag: The :class:`~.tagger.types.BasicTag` to look up.
            default: Substitute value when no frames exist; raises ``KeyError`` if left unset explicitly.

        Returns:
            Tuple of decoded text values or the provided fallback sequence.
        """
        result = tuple(t.value for t in self.tags if t.tag == tag)
        if len(result) == 0:
            if default is NO_DEFAULT_VALUE_LIST_STR:
                raise KeyError(f"{tag.value} is not in tags")
            return default
        return result

    def __init__(self, **kw: Any):
        """Construct a track row, accepting ``tags`` entity list or (for tests/convenience) a BasicTag->List mapping"""
        if "tags" not in kw and "tag" in kw and isinstance(kw["tag"], Mapping):
            t: Mapping[BasicTag, str | Sequence[str]] = kw["tag"]  # pyright: ignore[reportUnknownVariableType]
            kw["tags"] = [TagV(tag=tag, value=v) for tag, values in t.items() for v in ([values] if isinstance(values, str) else values)]
            del kw["tag"]
        super().__init__(**kw)

    def __lt__(self, other: Track | PictureFile | OtherFile):
        return self.filename < other.filename


class PictureFile(Base):
    """Standalone image file found inside an album directory at scan time.

    These files are candidates for embedding (or removal) when running cover-art checks.

    Attributes:
        album_picture_file_id: Primary key.
        album_id: Foreign key linking the image to its parent :class:`Album`.
        album: ORM back-reference to the owning album folder.
        filename: Basename of the image file on disk.
        file_size: Size in bytes.
        modify_timestamp: UNIX epoch last-write time.
        cover_source: ``True`` when this file was designated by the user as the album cover art source.
        picture_info: Composite property exposing resolution and format via :class:`~.picture.info.PictureInfo`.
    """

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

    def to_dict(self) -> dict[str, Any]:
        """Serialize image-file metadata for JSON export."""
        return {
            "filename": self.filename,
            "modify_timestamp": self.modify_timestamp,
            "cover_source": self.cover_source,
            "picture_info": self.picture_info.to_dict(),
        }

    def to_picture(self) -> Picture:
        """Convert this row into a plain ``Picture`` value object for tagger consumption."""
        return Picture(self.picture_info, PictureType.from_filename(self.filename), "")

    def __lt__(self, other: Track | PictureFile | OtherFile):
        return self.filename < other.filename


class OtherFile(Base):
    """Non-audio, non-image file encountered inside an album directory during a scan.

    These include audio or image files that were unreadable, and have been recorded so the scanner doesn't try to read
    them again. Or If the scanner detects other files like track lists or log files, they can be represented this way.

    Attributes:
        album_other_file_id: Primary key.
        album_id: Foreign key linking to the owning :class:`Album`.
        album: ORM back-reference to the parent album folder.
        filename: Basename on disk.
        file_size: Size in bytes.
        modify_timestamp: UNIX epoch last-write time.
    """

    __tablename__ = "album_other_file"
    __table_args__ = (Index("idx_album_other_file_album_id", "album_id"),)

    album_other_file_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("album.album_id"), nullable=False)
    album: Mapped[Optional[Album]] = relationship("Album", back_populates="other_files")

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    modify_timestamp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON export."""
        return {
            "filename": self.filename,
            "modify_timestamp": self.modify_timestamp,
            "file_size": self.file_size,
        }

    def __lt__(self, other: Track | PictureFile | OtherFile):
        return self.filename < other.filename


class Album(Base):
    """Top-level entity representing a physical album folder in the music library.

    Attributes:
        album_id: Primary key (auto-generated).
        path: Relative filesystem root for this album's files.
        scanner: Version of the library scanner that last modified this row; used to detect stale scans.
        collection_associations: Join rows linking this album to named :class:`CollectionEntity` groups.
        collections: Association proxy shortcut returning collection name strings.
        ignore_check_entities: Rows indicating which checks should be skipped for this album.
        ignore_checks: Association proxy shortcut returning suppressed check names as strings.
        other_files: Corrupt or non-audio/non-image files discovered during the scan.
        picture_files: Standalone :class:`PictureFile` images sitting in the folder.
        tracks: List of :class:`Track` audio files belonging to this album.
        created_at: UNIX timestamp when the row was first inserted (seconds since epoch).
        modified_at: UNIX timestamp marking last data mutation via checks or explicit edits.
    """

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

    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=lambda: int(datetime.now(UTC).timestamp()))
    modified_at: Mapped[int] = mapped_column(Integer, nullable=False, default=lambda: int(datetime.now(UTC).timestamp()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize album along with all nested tracks and files for JSON export."""
        return {
            "album_id": self.album_id,
            "path": self.path,
            "scanner": self.scanner,
            "collections": list(self.collections),
            "ignore_checks": list(self.ignore_checks),
            "tracks": [track.to_dict() for track in self.tracks],
            "picture_files": [picture_file.to_dict() for picture_file in self.picture_files],
            "other_files": [other_file.to_dict() for other_file in self.other_files],
            "created_at": datetime.fromtimestamp(self.created_at, UTC).isoformat() if self.created_at else None,
            "modified_at": datetime.fromtimestamp(self.modified_at, UTC).isoformat() if self.modified_at else None,
        }


class AlbumCollectionAssociation(Base):
    """Many-to-many join table linking albums to named collections.

    Attributes:
        album_collection_id: Primary key.
        album_id: Foreign key to :class:`Album`.
        collection_id: Foreign key to :class:`CollectionEntity`.
        collection: ORM back-reference to the target collection row.
        collection_name: Association proxy shortcut exposing the collection name.
        album: ORM back-reference to the linked album.
    """

    __tablename__ = "album_collection"

    album_collection_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)
    album_id: Mapped[int] = mapped_column(Integer, ForeignKey("album.album_id"))
    collection_id: Mapped[int] = mapped_column(Integer, ForeignKey("collection.collection_id"))

    collection: Mapped[CollectionEntity] = relationship()
    collection_name: AssociationProxy[str] = association_proxy("collection", "collection_name")

    album: Mapped[Album] = relationship(back_populates="collection_associations")


class ScanHistoryEntity(Base):
    """Per-full-scan audit row. Can be used to decide whether a full rescan is needed on next launch.

    Attributes:
        scan_history_id: Primary key.
        timestamp: UNIX epoch when the scan completed.
        folders_scanned: Number of top-level directories walked during this pass.
        albums_total: Count of unique album rows in the database after scanning finished.
    """

    __tablename__ = "scan_history"
    __table_args__ = (Index("idx_scan_history_timestamp", "timestamp"),)

    scan_history_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, primary_key=True)

    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    folders_scanned: Mapped[int] = mapped_column(Integer, nullable=False)
    albums_total: Mapped[int] = mapped_column(Integer, nullable=False)
