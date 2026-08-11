import logging
from pathlib import Path

import humanize

from albums.entities import Album, OtherFile, PictureFile, TagV, Track, TrackPicture
from albums.picture.format import format_to_mime_type
from albums.tagger.folder import AUDIO_FILE_SUFFIXES, AlbumTagger

from .folder import MiniStat, read_binary_file
from .remove_file import remove_file
from .scanner_types import MAX_IMAGE_SIZE, TargetRescan

logger = logging.getLogger(__name__)


def _scan_track(tagger: AlbumTagger, filename: str, stat: MiniStat, target_scan: TargetRescan | None) -> Track | None:
    with tagger.open(filename) as file:
        if target_scan is None or target_scan.streams:
            if file.has_video():  # check file streams
                return None
        else:
            if isinstance(target_scan.source, OtherFile):
                return None

        if target_scan is not None and not target_scan.tags and isinstance(target_scan.source, Track):
            tags = [TagV(tag=t.tag, value=t.value) for t in target_scan.source.tags]
            legacy_tags = list(target_scan.source.legacy_tags)
        else:
            tags = [TagV(tag=tag, value=value) for tag, values in file.get_tags() for value in values]
            legacy_tags = [tag_name for (tag_name, _) in file.get_legacy_tags()]

        if target_scan is not None and not target_scan.images and isinstance(target_scan.source, Track):
            pictures = [
                TrackPicture(picture_type=p.picture_type, picture_info=p.picture_info, description=p.description, embed_ix=p.embed_ix)
                for p in target_scan.source.pictures
            ]
        else:
            pictures = [
                TrackPicture(picture_type=picture.type, picture_info=picture.picture_info, description=picture.description, embed_ix=embed_ix)
                for embed_ix, picture in enumerate(picture for (picture, _data) in file.get_pictures())
            ]

        if target_scan is not None and not target_scan.streams and isinstance(target_scan.source, Track):
            stream = target_scan.source.stream
        else:
            stream = file.get_stream_info()

        return Track(
            filename=filename,
            file_size=stat.file_size,
            modify_timestamp=stat.modify_timestamp,
            stream=stream,
            pictures=pictures,
            tags=tags,
            legacy_tags=legacy_tags,
        )


def _scan_picture_file(tagger: AlbumTagger, filename: str, stat: MiniStat, scan_target: TargetRescan | None) -> PictureFile | None:
    if scan_target is not None and not scan_target.images and isinstance(scan_target.source, PictureFile):
        p = scan_target.source
        return PictureFile(filename=p.filename, modify_timestamp=p.modify_timestamp, cover_source=p.cover_source, picture_info=p.picture_info)

    if stat.file_size > MAX_IMAGE_SIZE:
        size = humanize.naturalsize(stat.file_size, binary=True)
        max = humanize.naturalsize(MAX_IMAGE_SIZE, binary=True)
        logger.warning(f"skipping image file {str(filename)} because it is {size} (albums max = {max})")
        return None

    expect_mime_type = format_to_mime_type(Path(filename).suffix.replace(".", ""))
    picture_info = tagger.get_picture_scanner().scan(read_binary_file(tagger.path() / filename), expect_mime_type)
    return PictureFile(filename=filename, modify_timestamp=stat.modify_timestamp, cover_source=False, picture_info=picture_info)


def scan_file(album: Album, tagger: AlbumTagger, path: Path, stat: MiniStat, target_scan: TargetRescan | None) -> None:
    cover_source = remove_file(album, path.name)

    if str.lower(path.suffix) in AUDIO_FILE_SUFFIXES:
        new_track = _scan_track(tagger, path.name, stat, target_scan)
        if new_track is None:
            album.other_files.append(OtherFile(filename=path.name, file_size=stat.file_size, modify_timestamp=stat.modify_timestamp))
        else:
            album.tracks.append(new_track)
    else:
        new_picture_file = _scan_picture_file(tagger, path.name, stat, target_scan)
        if new_picture_file is None:
            album.other_files.append(OtherFile(filename=path.name, file_size=stat.file_size, modify_timestamp=stat.modify_timestamp))
        else:
            new_picture_file.cover_source = cover_source
            album.picture_files.append(new_picture_file)
