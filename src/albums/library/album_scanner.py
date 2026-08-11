import itertools
import logging
from typing import List, Tuple

from albums.app import Context
from albums.picture.scan import PictureScannerCache
from albums.tagger.folder import AlbumTagger
from albums.types import Album, OtherFile, PictureFile, Track

from .file_scanner import scan_file
from .folder import MiniStat, stat_dir
from .remove_file import remove_file
from .scanner_types import AlbumScanResult, TargetRescan

logger = logging.getLogger(__name__)


def picture_cache(album: Album | None) -> PictureScannerCache:
    if not album:
        return {}
    return dict(
        itertools.chain(
            (
                ((pic.picture_info.file_size, pic.picture_info.file_hash), pic.picture_info)
                for track in sorted(album.tracks)
                for pic in track.pictures
            ),
            (((file.picture_info.file_size, file.picture_info.file_hash), file.picture_info) for file in sorted(album.picture_files)),
        )
    )


def _needs_rescan(scanner: int, file: Track | PictureFile | OtherFile) -> TargetRescan | None:
    if scanner < 6:
        return TargetRescan(file, tags=True, images=True, streams=True)
    if scanner < 7:
        return TargetRescan(file, tags=False, images=False, streams=True)  # v7 added more stream info
    if scanner < 8:
        return TargetRescan(file, tags=True, images=False, streams=False)  # v7 tags are sus due to orm issues
    if scanner == 8:
        return TargetRescan(file, tags=False, images=False, streams=True)  # v8 could incorrectly treat video as track after rescan
    return None


def scan_album(ctx: Context, tagger: AlbumTagger, album: Album, reread: bool = False) -> AlbumScanResult:
    album_path = ctx.config.library / album.path
    stored_files_list: List[Tuple[str, Tuple[MiniStat, PictureFile | Track | OtherFile]]] = [
        (t.filename, (MiniStat(t.file_size, t.modify_timestamp), t)) for t in album.tracks
    ]
    stored_files_list.extend((f.filename, (MiniStat(f.picture_info.file_size, f.modify_timestamp), f)) for f in album.picture_files)
    stored_files_list.extend((o.filename, (MiniStat(o.file_size, o.modify_timestamp), o)) for o in album.other_files)
    duplicate_files = set(filename for (filename, _) in stored_files_list if sum(1 if filename == fn else 0 for (fn, _) in stored_files_list) > 1)
    stored_files = dict(stored_files_list)
    updated = False
    for path, stat in stat_dir(album_path):
        if path.name in stored_files:
            (stored_stat, file) = stored_files[path.name]
            targeted = None
            if reread or stat != stored_stat or path.name in duplicate_files or (targeted := _needs_rescan(album.scanner, file)):
                logger.debug(f"re-scanning file: {str(path)}")
                scan_file(album, tagger, path, stat, targeted)
                updated = True  # TODO if reread==True, check whether file actually changed
            del stored_files[path.name]
        else:
            logger.debug(f"scanning new file: {str(path)}")
            scan_file(album, tagger, path, stat, None)
            updated = True
    for filename in stored_files:  # anything left has been deleted
        remove_file(album, filename)
        updated = True
    if len(album.tracks) == 0:
        return AlbumScanResult.REMOVED
    return AlbumScanResult.UPDATED if updated else AlbumScanResult.UNCHANGED
