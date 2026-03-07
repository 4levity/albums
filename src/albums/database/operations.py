import logging
from typing import Collection, Sequence

from sqlalchemy import Engine, delete, desc, select
from sqlalchemy.orm import Session

from ..tagger.types import BASIC_TAGS, BasicTag, Picture, PictureType, StreamInfo
from ..types import Album, PictureFile, ScanHistoryEntry, Track
from .models import (
    AlbumEntity,
    CollectionEntity,
    IgnoreCheckEntity,
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
        row = session.execute(select(AlbumEntity).where(AlbumEntity.album_id == album_id)).first()
        if row is None:
            raise ValueError(f"load_album called with invalid album_id={album_id}")
        return album_to_album(row[0], load_track_tags)


def album_to_album(entity: AlbumEntity, load_track_tags: bool) -> Album:
    return Album(
        entity.path,
        [_track(track, load_track_tags) for track in entity.tracks],
        [c.collection_name for c in entity.collections],
        [i.check_name for i in entity.ignore_checks],
        [_picture_file(picture_file) for picture_file in entity.picture_files],
        entity.album_id,
        entity.scanner,
    )


def _track(entity: TrackEntity, load_track_tags: bool) -> Track:
    tags: dict[BasicTag, list[str]] = {}
    if load_track_tags:
        for tag in entity.tags:
            if tag.name in BASIC_TAGS:
                tags.setdefault(BasicTag(tag.name), []).append(tag.value)
            else:
                logger.debug(f"ignoring tag {tag.name}")

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
        entity.file_info,
        picture_type,
        "",
    )


def _picture_file(entity: PictureFileEntity) -> PictureFile:
    return PictureFile(
        entity.filename,
        entity.file_info,
        entity.modify_timestamp,
        entity.cover_source,
    )


def add(db: Engine, album: Album) -> int:
    with Session(db) as session:
        collections = dict((row[0].collection_name, row[0]) for row in session.execute(select(CollectionEntity)).all())
        entity = AlbumEntity(path=album.path, scanner=album.scanner)
        for collection_name in album.collections:
            entity.collections.append(collections.get(collection_name, CollectionEntity(collection_name=collection_name)))
        for check_name in album.ignore_checks:
            entity.ignore_checks.append(IgnoreCheckEntity(check_name=check_name))
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
            entity.tags.append(TrackTagEntity(name=tag.value, value=value))
    return entity


def _picture_file_to_entity(file: PictureFile) -> PictureFileEntity:
    return PictureFileEntity(
        filename=file.filename,
        modify_timestamp=file.modify_timestamp,
        cover_source=file.cover_source,
        file_info=file.file_info,
    )


def _picture_to_entity(pic: Picture, embed_ix: int) -> TrackPictureEntity:
    return TrackPictureEntity(
        picture_type=pic.type,
        file_info=pic.file_info,
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
        all_collections = dict((row[0].collection_name, row[0]) for row in session.execute(select(CollectionEntity)).all())
        album = session.scalars(select(AlbumEntity).where(AlbumEntity.album_id == album_id)).one()
        album.collections.clear()
        for collection_name in collections:
            album.collections.append(all_collections.get(collection_name, CollectionEntity(collection_name=collection_name)))
        session.commit()


def update_ignore_checks(db: Engine, album_id: int, ignore_checks: Collection[str]):
    with Session(db) as session:
        album = session.scalars(select(AlbumEntity).where(AlbumEntity.album_id == album_id)).one()
        album.ignore_checks.clear()
        for check_name in ignore_checks:
            album.ignore_checks.append(IgnoreCheckEntity(check_name=check_name))
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
        row = session.execute(select(ScanHistoryEntity).order_by(desc(ScanHistoryEntity.timestamp))).first()
        if row is None:
            return None
        (entity,) = row
        return ScanHistoryEntry(entity.timestamp, entity.folders_scanned, entity.albums_total)
