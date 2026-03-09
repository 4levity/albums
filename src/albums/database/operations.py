import logging
from typing import Collection, Sequence

from sqlalchemy import Engine, delete, desc, select
from sqlalchemy.orm import Session

from ..tagger.types import BasicTag, Picture, PictureType, StreamInfo
from ..types import Album, PictureFile, ScanHistoryEntry, Track
from .models import (
    AlbumEntity,
    PictureFileEntity,
    ScanHistoryEntity,
    TrackEntity,
    TrackPictureEntity,
    TrackTagEntity,
)

logger = logging.getLogger(__name__)

PICTURE_TYPE_FRONT_COVER_SOURCE_FILE = 200


def load_album(db: Engine, album_id: int, load_track_tags: bool = True) -> Album:
    with Session(db) as session:
        row = session.execute(select(AlbumEntity).where(AlbumEntity.album_id == album_id)).tuples().first()
        if row is None:
            raise ValueError(f"load_album called with invalid album_id={album_id}")
        return album_to_album(row[0], load_track_tags)


def album_to_album(entity: AlbumEntity, load_track_tags: bool = True) -> Album:
    return Album(
        entity.path,
        [track_from_entity(track, load_track_tags) for track in entity.tracks],
        list(entity.collections),
        list(entity.ignore_checks),
        [picture_file_from_entity(picture_file) for picture_file in entity.picture_files],
        entity.album_id,
        entity.scanner,
    )


def track_from_entity(entity: TrackEntity, load_track_tags: bool = True) -> Track:
    tags: dict[BasicTag, list[str]] = {}
    if load_track_tags:
        for tag_entity in entity.tags:
            tags.setdefault(tag_entity.tag, []).append(tag_entity.value)

    return Track(
        entity.filename,
        dict((tag, tuple(values)) for tag, values in tags.items()),
        entity.file_size,
        entity.modify_timestamp,
        entity.stream,
        [_picture(picture, PictureType(picture.picture_type)) for picture in entity.pictures],
    )


def _picture(entity: TrackPictureEntity | PictureFileEntity, picture_type: PictureType) -> Picture:
    return Picture(
        entity.picture_info,
        picture_type,
        "",
    )


def picture_file_from_entity(entity: PictureFileEntity) -> PictureFile:
    return PictureFile(
        entity.filename,
        entity.picture_info,
        entity.modify_timestamp,
        entity.cover_source,
    )


def add(db: Engine, album: Album) -> int:
    with Session(db) as session:
        entity = AlbumEntity(path=album.path, scanner=album.scanner)
        for collection_name in album.collections:
            entity.collections.append(collection_name)
        for check_name in album.ignore_checks:
            entity.ignore_checks.append(check_name)
        for track in album.tracks:
            entity.tracks.append(_track_to_entity(track))
        for picture_file in album.picture_files:
            entity.picture_files.append(_picture_file_to_entity(picture_file))
        session.add(entity)
        session.commit()
        if entity.album_id is None:
            raise RuntimeError("no album_id after add")
        return entity.album_id


def _track_to_entity(track: Track) -> TrackEntity:
    entity = TrackEntity(
        filename=track.filename,
        file_size=track.file_size,
        modify_timestamp=track.modify_timestamp,
        stream=track.stream if track.stream else StreamInfo(),
    )
    for embed_ix, picture in enumerate(track.pictures):
        entity.pictures.append(_picture_to_entity(picture, embed_ix))
    for tag, values in track.tags.items():
        for value in values:
            entity.tags.append(TrackTagEntity(tag=tag, value=value))
    return entity


def _picture_file_to_entity(file: PictureFile) -> PictureFileEntity:
    return PictureFileEntity(
        filename=file.filename,
        modify_timestamp=file.modify_timestamp,
        cover_source=file.cover_source,
        picture_info=file.picture_info,
    )


def _picture_to_entity(pic: Picture, embed_ix: int) -> TrackPictureEntity:
    return TrackPictureEntity(
        picture_type=pic.type,
        picture_info=pic.picture_info,
        description=pic.description,
        embed_ix=embed_ix,
    )


def remove(db: Engine, album_id: int):
    with Session(db) as session:
        result = session.execute(delete(AlbumEntity).where(AlbumEntity.album_id == album_id))
        if result.rowcount != 1:  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            logger.warning(f"didn't delete album, not found: {album_id}")
        session.commit()


def update_scanner(db: Engine, album_id: int, scanner_version: int):
    with Session(db) as session:
        album = session.scalars(select(AlbumEntity).where(AlbumEntity.album_id == album_id)).one()
        album.scanner = scanner_version
        session.commit()


def update_collections(db: Engine, album_id: int, collections: Collection[str]):
    with Session(db) as session:
        album = session.execute(select(AlbumEntity).where(AlbumEntity.album_id == album_id)).tuples().one()[0]
        old_collections = set(album.collections)
        new_collections = set(collections)
        for collection_name in new_collections - old_collections:
            album.collections.append(collection_name)
        for collection_name in old_collections - new_collections:
            album.collections.remove(collection_name)
        session.commit()


def update_ignore_checks(db: Engine, album_id: int, ignore_checks: Collection[str]):
    with Session(db) as session:
        album = session.scalars(select(AlbumEntity).where(AlbumEntity.album_id == album_id)).one()
        old_ignore_checks = set(album.ignore_checks)
        new_ignore_checks = set(ignore_checks)
        for check_name in new_ignore_checks - old_ignore_checks:
            album.ignore_checks.append(check_name)
        for check_name in old_ignore_checks - new_ignore_checks:
            album.ignore_checks.remove(check_name)
        session.commit()


def update_tracks(db: Engine, album_id: int, tracks: Sequence[Track]):
    with Session(db) as session:
        album = session.scalars(select(AlbumEntity).where(AlbumEntity.album_id == album_id)).one()
        album.tracks.clear()
        album.tracks = [_track_to_entity(track) for track in tracks]
        session.commit()


def update_picture_files(db: Engine, album_id: int, picture_files: Sequence[PictureFile]):
    with Session(db) as session:
        album = session.scalars(select(AlbumEntity).where(AlbumEntity.album_id == album_id)).one()
        album.picture_files = [_picture_file_to_entity(file) for file in picture_files]
        session.commit()


def record_full_scan(db: Engine, entry: ScanHistoryEntry):
    with Session(db) as session:
        session.add(ScanHistoryEntity(timestamp=entry.timestamp, folders_scanned=entry.folders_scanned, albums_total=entry.albums_total))
        session.commit()


def get_last_scan_info(db: Engine) -> ScanHistoryEntry | None:
    with Session(db) as session:
        row = session.execute(select(ScanHistoryEntity).order_by(desc(ScanHistoryEntity.timestamp))).tuples().first()
        if row is None:
            return None
        (entity,) = row
        return ScanHistoryEntry(entity.timestamp, entity.folders_scanned, entity.albums_total)
